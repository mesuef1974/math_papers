#!/usr/bin/env python3
"""المشغّل المجدوَل: بطاقة ready → worktree → claude بصلاحيات مخفَّضة → فحص محلي → PR. كل خطوة حدث في الدفتر.

الصلاحيات: النموذج يكتب الشيفرة ويشغّل الاختبارات فقط. الدفع وفتح الطلب يفعلهما هذا السكربت بعد نجاح
prepush_check.py، والدمج بوابة CI وطابور الدمج. حارس .claude/hooks/guard_git.py يحجب ما يتسرّب.
قائمة الأدوات تضيّق لا تعزل (اختبار يكتبه النموذج يشغّل ما يشاء)، فبيئة الجلسة الآلية نفسها بلا دفع
(`model_env`: عنوان دفع معطَّل ورمز gh غير صالح)، والفرع الذي يمسّ حارسًا أو ملف CI لا يُدفع آليًا.

    python automation/runner.py --once [--dry-run] [--max-turns 40] [--model <id>]
يُجدوَل كل N دقائق (automation/schedule.py)؛ قفل automation/.lock يمنع تشغيلين متوازيين.
بلا بطاقة ready لا يُستدعى النموذج ولا يُستهلك شيء.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ledger  # noqa: E402
import sync  # noqa: E402
from merge_gate import ALWAYS_FORBIDDEN, path_forbidden  # noqa: E402

ROOT = ledger.ROOT
WORKTREES = ROOT / ".worktrees"
LOCK = ROOT / "automation" / ".lock"
LOCK_STALE_SECONDS = 3 * 60 * 60
REQUIRED_TOOLS = ("claude", "git", "gh")
HEARTBEAT_KEEP = 200
PUSH_DISABLED = "push-disabled://runner-model"
GH_NO_AUTH = "runner-model-no-auth"
# بلا تثبيت تأخذ الجلسة الآلية نموذج المستخدم الافتراضي، وهو الأغلى عادة (قرار المالك 2026-11-26).
DEFAULT_MODEL = "claude-sonnet-5-5"
USAGE_KEYS = {
    "input": "inputTokens",
    "cache_write": "cacheCreationInputTokens",
    "cache_read": "cacheReadInputTokens",
    "output": "outputTokens",
}

# الجلسة الآلية بلا من يوافق: ما لم يُسمح به هنا يُرفض، فبلا هذه القائمة لا اختبار يُشغَّل ولا إيداع يُكتب.
GUIDE_EXTRACT_PYTHON = "C:/Users/mesue/.venvs/guide_extract/Scripts/python"  # بيئة OpenCV وpymupdf (`tools/extraction/README.md`)
ALLOWED_TOOLS = [
    "Read",
    "Edit",
    "Write",
    "Glob",
    "Grep",
    "Bash(python manage.py *)",
    "Bash(python -m pytest *)",
    "Bash(python -m ruff *)",
    "Bash(python scripts/prepush_check.py *)",
    "Bash(pytest *)",
    "Bash(ruff *)",
    "Bash(npm --prefix frontend *)",
    "Bash(git status*)",
    "Bash(git diff*)",
    "Bash(git log*)",
    "Bash(git add *)",
    "Bash(git commit *)",
    # خط الاستخراج (`tools/extraction`) ببيئته المحلية: مرحلة المقرر واختباراتها وحدهما، لا بايثون مطلق (قرار المالك 2026-11-20)
    f"Bash({GUIDE_EXTRACT_PYTHON} -m tools.extraction *)",
    f"Bash({GUIDE_EXTRACT_PYTHON} -m pytest *)",
]

DISALLOWED_TOOLS = [
    "Bash(git push*)",
    "Bash(git merge*)",
    "Bash(git rebase*)",
    "Bash(gh pr merge*)",
    "Bash(gh *)",
    "Bash(railway*)",
    "Bash(rm -rf*)",
    "WebFetch",
]

PROMPT = """أنت تنفّذ بطاقة عمل واحدة في مستودع Django + Vue. اعمل داخل هذا المجلد فقط.

العنوان: {title}
المطلوب:
{body}

ما يُعدّ نجاحًا (يجب أن يتحقق باختبار أو سلوك قابل للتشغيل):
{success}

القواعد:
- لا تعدّل ملفات .github/ أو scripts/ أو security/ أو lockfiles أو requirements*.txt أو Dockerfile أو railway.toml.
- كل تغيير في النماذج يرافقه makemigrations، وكل منطق في services.py لا في النماذج أو العروض.
- أضف اختبارًا يفشل قبل تغييرك وينجح بعده.
- الأمر python هو بايثون المشروع، وقاعدة الاختبار مضبوطة في البيئة (DATABASE_URL)؛ لا تغيّرهما.
- في النهاية شغّل: python scripts/prepush_check.py --allow-missing، وأصلح ما يفشل.
- أودع تغييراتك بـ git add <مسارات صريحة> ثم git commit برسالة عربية واضحة. لا تدفع.
"""


def sh(cmd: list[str], cwd: Path = ROOT, check: bool = True, **kw) -> subprocess.CompletedProcess:
    # على ويندوز لا تظهر نافذة طرفية لأي أمر فرعي (قرار المالك)
    kw.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return subprocess.run(cmd, cwd=cwd, text=True, encoding="utf-8", errors="replace", check=check, **kw)


def acquire_lock() -> bool:
    if LOCK.exists():
        age = time.time() - LOCK.stat().st_mtime
        if age < LOCK_STALE_SECONDS:
            print(f"مشغّل آخر يعمل (قفل عمره {int(age)} ث) — خروج")
            return False
        print("قفل قديم — يُزال")
        LOCK.unlink()
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock() -> None:
    LOCK.unlink(missing_ok=True)


def pick_card() -> str | None:
    ready = ledger.cards_in("ready")
    return ready[0] if ready else None


def make_worktree(card: str) -> tuple[Path, str]:
    WORKTREES.mkdir(exist_ok=True)
    branch = f"card/{card}"
    path = WORKTREES / card
    sh(["git", "fetch", "origin", "main"], check=False)
    if path.exists():
        return path, branch
    sh(["git", "worktree", "add", "-b", branch, str(path), "origin/main"])
    return path, branch


def work_env(card: str) -> dict[str, str]:
    """بيئة النموذج والفحص: python المشروع أول المسار، وقاعدة اختبار SQLite خارج المستودع إن لم تُضبط قاعدة."""
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    if not env.get("DATABASE_URL"):
        db = Path(tempfile.gettempdir()) / "math_papers_runner" / f"{card}.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        env["DATABASE_URL"] = f"sqlite:///{db.as_posix()}"
    return env


def model_env(card: str) -> dict[str, str]:
    """بيئة الجلسة الآلية: بيئة العمل بلا قدرة على النشر. git يدفع إلى عنوان معطَّل، وgh برمز غير صالح
    (يسبق الرمز المخزَّن)، فلا يدفع النموذج ولا يفتح طلبًا ولو من داخل بايثون. الجلب يبقى يعمل."""
    env = work_env(card)
    count = int(env.get("GIT_CONFIG_COUNT") or 0)
    env[f"GIT_CONFIG_KEY_{count}"] = "remote.origin.pushurl"
    env[f"GIT_CONFIG_VALUE_{count}"] = PUSH_DISABLED
    env["GIT_CONFIG_COUNT"] = str(count + 1)
    env["GH_TOKEN"] = env["GITHUB_TOKEN"] = GH_NO_AUTH
    return env


def model_command(model: str | None, max_turns: int) -> list[str]:
    """النص يُمرَّر على الدخل القياسي: الخيارات متعددة القيم تبتلع أي وسيط موضعي يليها."""
    cmd = [shutil.which("claude") or "claude", "-p", "--max-turns", str(max_turns)]
    cmd += ["--permission-mode", "acceptEdits", "--output-format", "json"]
    if model:
        cmd += ["--model", model]
    return [*cmd, "--allowedTools", *ALLOWED_TOOLS, "--disallowedTools", *DISALLOWED_TOOLS]


def parse_result(stdout: str) -> tuple[str, dict]:
    """نص الجلسة واستهلاكها من خرج `--output-format json`. `modelUsage` يشمل الوكلاء الفرعيين.
    خرج غير مفهوم (انقطاع أو خطأ قبل البدء) يُعاد كما هو بلا استهلاك: القياس لا يُسقط البطاقة."""
    try:
        data = json.loads(stdout)
        models = data["modelUsage"]
        usage = {key: sum(m.get(src, 0) for m in models.values()) for key, src in USAGE_KEYS.items()}
        usage |= {"models": sorted(models), "turns": data.get("num_turns")}
        usage["cost_usd"] = data.get("total_cost_usd")
    except (ValueError, KeyError, TypeError, AttributeError):
        return stdout, {}
    return str(data.get("result") or data.get("subtype") or ""), usage


def run_model(path: Path, card: str, model: str | None, max_turns: int) -> tuple[int, dict]:
    meta = ledger.first(card) or {}
    prompt = PROMPT.format(
        title=meta.get("title", card),
        body=meta.get("body", ""),
        success=meta.get("success", "غير محدد — حدّده أولًا في الاختبار"),
    )
    proc = sh(
        model_command(model, max_turns),
        cwd=path,
        check=False,
        input=prompt,
        capture_output=True,
        env=model_env(card),
    )
    # مخرجات الجلسة الآلية بجوار شجرة العمل (المجلد خارج git) لمراجعة ما فعله النموذج.
    log = WORKTREES / f"{card}.log"
    text, usage = parse_result(proc.stdout or "")
    log.write_text(text + (proc.stderr or ""), encoding="utf-8")
    return proc.returncode, usage


def unpushable(path: Path) -> str:
    """سبب يمنع الدفع، أو نص فارغ. فرع بلا إيداع يُفشل فتح الطلب، وتعديل غير مودَع يعني عملًا ناقصًا."""
    ahead = sh(
        ["git", "rev-list", "--count", "origin/main..HEAD"], cwd=path, capture_output=True
    ).stdout.strip()
    if not int(ahead or 0):
        return "لا إيداعات فوق origin/main"
    status = sh(["git", "status", "--porcelain"], cwd=path, capture_output=True).stdout.splitlines()
    dirty = [line[3:] for line in status]
    if dirty:
        return "تعديلات غير مودَعة: " + "، ".join(dirty[:5])
    changed = sh(
        ["git", "diff", "--name-only", "origin/main...HEAD"], cwd=path, capture_output=True
    ).stdout.split()
    guarded = [f for f in changed if path_forbidden(f, ALWAYS_FORBIDDEN)]
    if guarded:
        # الفحص المحلي يُشغَّل من نسخة الفرع: فرع عدّل الحارس أو الفحص لا يشهد لنفسه.
        return "الفرع يمسّ مسارات محروسة (دفعها بيد المالك): " + "، ".join(guarded[:5])
    return ""


def prepush(path: Path, card: str, head: str) -> dict[str, str] | None:
    """الفحص الصارم (أداة غائبة فشل، لا نجاح صامت) ثم بصمته: ما قيس، وعلى أي رأس. None = لا يُدفع."""
    receipt = path / ".prepush_receipt"
    receipt.unlink(missing_ok=True)
    proc = sh([sys.executable, "scripts/prepush_check.py"], cwd=path, check=False, env=work_env(card))
    if proc.returncode != 0 or not receipt.exists():
        return None
    data = json.loads(receipt.read_text(encoding="utf-8"))
    checks = data.get("checks") or {}
    if data.get("head") != head or not checks or any(v != "ok" for v in checks.values()):
        return None
    return checks


def push_and_open_pr(path: Path, branch: str, card: str) -> str:
    sh(["git", "push", "-u", "origin", branch], cwd=path)
    meta = ledger.first(card) or {}
    body = f"بطاقة `{card}`\n\n{meta.get('body', '')}\n\nالنجاح: {meta.get('success', '')}\n\n(يُكتب سطر الاعتماد هنا بعد المراجعة: اعتُمد من المالك — YYYY-MM-DD — الرأس sha8)"
    proc = sh(
        [
            "gh",
            "pr",
            "create",
            "--base",
            "main",
            "--head",
            branch,
            "--title",
            meta.get("title", card),
            "--body",
            body,
        ],
        cwd=path,
        capture_output=True,
    )
    return proc.stdout.strip()


def heartbeat(outcome: str) -> None:
    """سطر لكل تشغيل في .worktrees/runner.log: conhost --headless لا يعيد رمز الخروج إلى Task Scheduler،
    فهذا السجل هو الدليل أن المهمة المجدولة تعمل فعلًا وأن أدواتها على المسار."""
    WORKTREES.mkdir(exist_ok=True)
    log = WORKTREES / "runner.log"
    missing = [tool for tool in REQUIRED_TOOLS if not shutil.which(tool)]
    line = f"{ledger.now()} {outcome}"
    if missing:
        line += f" | غائب عن المسار: {', '.join(missing)}"
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    log.write_text("\n".join([*lines, line][-HEARTBEAT_KEEP:]) + "\n", encoding="utf-8")


def run_card(card: str, model: str | None, max_turns: int) -> tuple[int, str]:
    """رمز الخروج ووصف ما انتهى إليه التشغيل."""
    try:
        ledger.append(card, "claimed", pid=os.getpid())
        path, branch = make_worktree(card)
        rc, usage = run_model(path, card, model, max_turns)
        head = sh(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True).stdout.strip()
        ledger.append(card, "coded", exit_code=rc, head=head, usage=usage)
        if reason := unpushable(path):
            ledger.append(card, "blocked", reason=reason, head=head)
            return 1, f"{card}: لا دفع: {reason} — راجع .worktrees/{card}.log"
        checks = prepush(path, card, head)
        if checks is None:
            ledger.append(card, "prepush_failed", head=head)
            return 1, f"{card}: الفحص المحلي فشل — البطاقة تبقى في worktree للمراجعة"
        ledger.append(card, "prepush_ok", head=head, checks=sorted(checks))
        url = push_and_open_pr(path, branch, card)
        ledger.append(card, "pr_opened", url=url, head=head)
        return 0, f"{card}: PR {url}"
    finally:
        release_lock()


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-turns", type=int, default=40)
    args = ap.parse_args(argv)

    card = pick_card()
    if args.dry_run:
        print(
            f"سيُلتقط: {card} → worktree .worktrees/{card} → claude → prepush → PR"
            if card
            else "لا بطاقات ready"
        )
        return 0
    synced = sync.quiet()
    if not card:
        code, outcome = 0, "لا بطاقات ready" + (f" | مزامنة: {synced}" if synced else "")
    elif not acquire_lock():
        code, outcome = 0, "مشغّل آخر يعمل"
    else:
        try:
            code, outcome = run_card(card, args.model, args.max_turns)
        except Exception as exc:
            heartbeat(f"{card}: خطأ: {exc!r}")
            raise
    print(outcome)
    heartbeat(outcome)
    return code


if __name__ == "__main__":
    sys.exit(main())
