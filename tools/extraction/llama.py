"""خادم llama-server محلي لنموذج رؤية، يُشغَّل ويُغلق آليًا، وعميل أسئلة الصور بمخطط JSON.

المحرك والنماذج خارج المستودع: الإعداد `vision` في book.yaml (engine وvendor وmodels ومجلد النماذج ونموذجا small وlarge)، والافتراضات
تطابق محرك LM Studio (قراءة فقط) ومجلد `~/.cache/guide_extract/models`. بلا نافذة (CREATE_NO_WINDOW)، وسجل الخادم في ملف بمجلد الكتاب.
يُغلق في `finally` وatexit ومؤقّت خمول (ttl) وعمر أقصى؛ كل طلب من العميل يجدّد الخمول. على كرت 8 غ.ب لا يجتمع مع PaddleOCR (انظر ocr.py).
"""

from __future__ import annotations

import atexit
import base64
import json
import os
import subprocess
import threading
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .config import Book

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
HOME = Path.home()
DEFAULTS: dict[str, Any] = {
    "engine": str(
        HOME / ".lmstudio/extensions/backends/llama.cpp-win-x86_64-nvidia-cuda12-avx2-2.70.0/llama-server.exe"
    ),
    "vendor": str(HOME / ".lmstudio/extensions/backends/vendor/win-llama-cuda12-vendor-v2"),
    "models_dir": str(HOME / ".cache/guide_extract/models"),
    "models": {
        "small": {
            "model": "Qwen3VL-4B-Instruct-Q4_K_M.gguf",
            "mmproj": "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf",
        },
        "large": {
            "model": "Qwen3VL-8B-Instruct-Q4_K_M.gguf",
            "mmproj": "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf",
        },
    },
    "port": 8071,
    "ttl": 300,  # ثوانٍ خمول قبل الإغلاق
    "max_life": 14400,
    "startup_timeout": 240,
    "contexts": {"small": 16384, "large": 8192},  # سياق كل حجم (الصور الكبيرة تحتاج الأكبر مع النموذج الصغير)
}


def settings(book: Book) -> dict[str, Any]:
    over = book.get("vision", {})
    return {
        **DEFAULTS,
        **over,
        "models": {**DEFAULTS["models"], **over.get("models", {})},
        "contexts": {**DEFAULTS["contexts"], **over.get("contexts", {})},
    }


def command(cfg: dict[str, Any], size: str, ctx: int | None = None) -> list[str]:
    """سطر تشغيل الخادم لحجم النموذج (small/large)؛ يرفع KeyError بحجم غير معروف."""
    spec = cfg["models"][size]
    models = Path(cfg["models_dir"])
    return [
        str(cfg["engine"]),
        "-m",
        str(models / spec["model"]),
        "-ngl",
        "99",
        "-c",
        str(ctx or cfg["contexts"][size]),
        "--host",
        "127.0.0.1",
        "--port",
        str(cfg["port"]),
        "--mmproj",
        str(models / spec["mmproj"]),
    ]


def image_part(path: Path) -> dict[str, Any]:
    data = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}}


def _kill(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(  # noqa: S603
            ["taskkill", "/PID", str(pid), "/T", "/F"],  # noqa: S607
            capture_output=True,
            creationflags=NO_WINDOW,
        )
    else:
        try:
            os.kill(pid, 15)
        except OSError:
            pass


class Server:
    def __init__(self, port: int, ttl: float, max_life: float):
        self.port, self.ttl, self.max_life = port, ttl, max_life
        self.last = time.monotonic()
        self.proc: subprocess.Popen[bytes] | None = None
        self._stop = threading.Event()

    def touch(self) -> None:
        self.last = time.monotonic()

    def close(self) -> None:
        self._stop.set()
        if self.proc and self.proc.poll() is None:
            _kill(self.proc.pid)

    def watch(self, started: float) -> None:
        while not self._stop.wait(2):
            now = time.monotonic()
            dead = self.proc is None or self.proc.poll() is not None
            if dead or now - self.last > self.ttl or now - started > self.max_life:
                self.close()
                return

    def chat(self, messages: list[dict[str, Any]], **params: Any) -> dict[str, Any]:
        self.touch()
        body = json.dumps({"messages": messages, "stream": False, **params}).encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/completions", body, {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=900) as response:  # noqa: S310
            out = json.load(response)
        self.touch()
        return out


@contextmanager
def serve(book: Book, size: str = "small", ctx: int | None = None) -> Iterator[Server]:
    """يشغّل الخادم ويُرجعه جاهزًا (health) ثم يغلقه عند الخروج."""
    cfg = settings(book)
    cmd = command(cfg, size, ctx)
    engine = Path(cfg["engine"])
    log_path = book.out / "llama_server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("wb")
    server = Server(cfg["port"], cfg["ttl"], cfg["max_life"])
    env = {**os.environ, "PATH": f"{cfg['vendor']};{engine.parent};{os.environ['PATH']}"}
    try:
        server.proc = subprocess.Popen(  # noqa: S603
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
            cwd=engine.parent,
            env=env,
        )
        atexit.register(server.close)
        threading.Thread(target=server.watch, args=(time.monotonic(),), daemon=True).start()
        deadline = time.monotonic() + cfg["startup_timeout"]
        while time.monotonic() < deadline:
            if server.proc.poll() is not None:
                raise RuntimeError(f"توقف الخادم عند البدء، انظر السجل: {log_path}")
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cfg['port']}/health", timeout=2)  # noqa: S310
                break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError("انتهت مهلة بدء الخادم")
        yield server
    finally:
        server.close()
        log.close()


def asker(server: Any):
    """عميل `ask(صورة، سؤال، مخطط) -> dict` فوق خادم له chat(messages, **params). جواب غير JSON يُرجع {}."""

    def ask(image: Path, question: str, fmt: dict[str, Any]) -> dict[str, Any]:
        reply = server.chat(
            [{"role": "user", "content": [image_part(image), {"type": "text", "text": question}]}],
            response_format=fmt,
            temperature=0,
            max_tokens=400,
        )
        try:
            return json.loads(reply["choices"][0]["message"]["content"])
        except (ValueError, KeyError, IndexError):
            return {}

    return ask
