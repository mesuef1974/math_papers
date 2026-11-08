"""مشرف خادم المعاينة: يغلقه آليًا بالكود لا بنموذج ولا بتدخل، ولا يكلّف أي توكنز.

الإغلاق يقع في أحد هذه الأحوال، وكلها داخل finally وatexit والإشارات:
  1. خمول: لا نشاط في ملف السجل أكثر من --ttl ثانية (كل طلب يكتب سطرًا في سجل runserver فيتجدد النشاط).
  2. عمر أقصى: --max-life ثانية مهما كان النشاط.
  3. انتهاء الابن بنفسه، أو Ctrl+C، أو إشارة إنهاء، أو خروج المشرف لأي سبب.
  4. `stop`: يغلق خادمًا قائمًا من ملف pid (للتنظيف اليدوي أو من مراقب خارجي).

على ويندوز لا تظهر نافذة (CREATE_NO_WINDOW)، والسجل في ملف بدل النافذة. الاستعمال:
    python scripts/preview_server.py start [--port 8047] [--ttl 900] [--max-life 7200]
    python scripts/preview_server.py stop  [--port 8047]
"""

from __future__ import annotations

import argparse
import atexit
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# مسار ثابت لا يتبع TEMP، فتراه كل سياقات التشغيل (المهمة المجدولة والجلسة والطرفية) فلا تتكرر النسخة
STATE_DIR = Path.home() / ".cache" / "math_papers_preview"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NEW_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def state_paths(port: int) -> tuple[Path, Path]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / f"preview_{port}.pid", STATE_DIR / f"preview_{port}.log"


def alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(  # noqa: S603
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],  # noqa: S607
            capture_output=True,
            text=True,
            creationflags=NO_WINDOW,
        ).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def kill_tree(pid: int) -> None:
    """يغلق العملية وأبناءها. لا يرمي إن كانت انتهت."""
    if os.name == "nt":
        subprocess.run(  # noqa: S603
            ["taskkill", "/PID", str(pid), "/T", "/F"],  # noqa: S607
            capture_output=True,
            creationflags=NO_WINDOW,
        )
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except OSError:
        pass


def _interrupt(*_: object) -> None:
    raise KeyboardInterrupt


def supervise(
    cmd: list[str],
    *,
    ttl: float,
    max_life: float,
    log_path: Path,
    pid_path: Path,
    poll: float = 1.0,
    env: dict[str, str] | None = None,
    cwd: Path = ROOT,
) -> str:
    """يشغّل الأمر ويراقبه حتى يُغلقه. يعيد سبب الإغلاق: exited | idle | max_life | interrupted."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("ab", buffering=0)
    child = subprocess.Popen(  # noqa: S603
        cmd,
        cwd=cwd,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=NO_WINDOW | NEW_GROUP,
        start_new_session=os.name != "nt",
    )
    pid_path.write_text(str(child.pid), encoding="utf-8")

    def cleanup() -> None:
        if child.poll() is None:
            kill_tree(child.pid)
        pid_path.unlink(missing_ok=True)
        log.close()

    atexit.register(cleanup)
    reason = "exited"
    previous = {}
    try:
        for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
            sig = getattr(signal, name, None)
            if sig is not None:
                previous[sig] = signal.signal(sig, _interrupt)
        started, started_wall = time.monotonic(), time.time()
        while child.poll() is None:
            now = time.monotonic()
            idle_for = time.time() - max(log_path.stat().st_mtime, started_wall)
            if now - started >= max_life:
                reason = "max_life"
                break
            if idle_for >= ttl:
                reason = "idle"
                break
            time.sleep(poll)
    except KeyboardInterrupt:
        reason = "interrupted"
    finally:
        cleanup()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return reason


def port_busy(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def running(port: int) -> bool:
    """يعمل خادمنا (pid حي) أو المنفذ مشغول بأي شيء."""
    pid_path, _ = state_paths(port)
    try:
        if alive(int(pid_path.read_text(encoding="utf-8"))):
            return True
    except (OSError, ValueError):
        pass
    return port_busy(port)


def stale_pids(port: int) -> list[int]:
    """عمليات runserver على منفذنا بلا ملف pid (شيم uv يولّد حفيدًا، وويندوز يسمح بمستمعَين على المنفذ نفسه)."""
    needle = f"runserver 127.0.0.1:{port}"
    if os.name == "nt":
        script = (
            "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | Where-Object { $_.CommandLine -like '*"
            + needle
            + "*' } | ForEach-Object { $_.ProcessId }"
        )
        cmd = ["powershell", "-NoProfile", "-Command", script]
    else:
        cmd = ["pgrep", "-f", needle]
    out = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW).stdout  # noqa: S603
    return [int(x) for x in out.split() if x.isdigit() and int(x) != os.getpid()]


def stop(port: int) -> bool:
    pid_path, _ = state_paths(port)
    stopped = False
    if pid_path.exists():
        pid = int(pid_path.read_text(encoding="utf-8") or 0)
        if pid and alive(pid):
            kill_tree(pid)
        pid_path.unlink(missing_ok=True)
        stopped = True
    for pid in stale_pids(port):
        kill_tree(pid)
        stopped = True
    return stopped


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("start")
    start.add_argument("--port", type=int, default=8047)
    start.add_argument("--ttl", type=float, default=900)
    start.add_argument("--max-life", type=float, default=7200)
    start.add_argument(
        "--if-not-running", action="store_true", help="لا تبدأ نسخة ثانية إن كان خادم المنفذ يعمل"
    )
    stopper = sub.add_parser("stop")
    stopper.add_argument("--port", type=int, default=8047)
    args = parser.parse_args()

    if args.action == "stop":
        print("أُغلق" if stop(args.port) else "لا خادم قائم")
        return 0

    pid_path, log_path = state_paths(args.port)
    if args.if_not_running and running(args.port):
        print("الخادم يعمل، لا نسخة ثانية")
        return 0
    stop(args.port)  # لا يتراكم خادم قديم على المنفذ نفسه
    log_path.write_bytes(b"")
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings.production"),
        "SECRET_KEY": os.environ.get("SECRET_KEY", "preview-only-key"),
        "ALLOWED_HOSTS": "127.0.0.1,localhost",
        "SECURE_SSL_REDIRECT": "0",
        "DATABASE_URL": os.environ.get(
            "DATABASE_URL", f"sqlite:///{Path.home().as_posix()}/.cache/math_papers_preview.db"
        ),
    }
    cmd = [sys.executable, "manage.py", "runserver", f"127.0.0.1:{args.port}", "--noreload", "--insecure"]
    print(f"السجل: {log_path}  | يُغلق بعد {args.ttl:.0f}ث خمول أو {args.max_life:.0f}ث عمرًا")
    reason = supervise(
        cmd, ttl=args.ttl, max_life=args.max_life, log_path=log_path, pid_path=pid_path, env=env
    )
    print(f"أُغلق الخادم: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
