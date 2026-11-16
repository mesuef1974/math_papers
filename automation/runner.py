#!/usr/bin/env python3
"""المشغّل المجدوَل: بطاقة ready → worktree → claude بصلاحيات مخفَّضة → فحص محلي → PR. كل خطوة حدث في الدفتر.

الصلاحيات: النموذج يكتب الشيفرة ويشغّل الاختبارات فقط. الدفع وفتح الطلب يفعلهما هذا السكربت بعد نجاح
prepush_check.py، والدمج بوابة CI وطابور الدمج. حارس .claude/hooks/guard_git.py يحجب ما يتسرّب.

    python automation/runner.py --once [--dry-run] [--max-turns 40] [--model <id>]
يُجدوَل كل N دقائق (automation/schedule.py)؛ قفل automation/.lock يمنع تشغيلين متوازيين.
بلا بطاقة ready لا يُستدعى النموذج ولا يُستهلك شيء.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger  # noqa: E402

ROOT = ledger.ROOT
WORKTREES = ROOT / ".worktrees"
LOCK = ROOT / "automation" / ".lock"
LOCK_STALE_SECONDS = 3 * 60 * 60

# الجلسة الآلية بلا من يوافق: ما لم يُسمح به هنا يُرفض، فبلا هذه القائمة لا اختبار يُشغَّل ولا إيداع يُكتب.
ALLOWED_TOOLS = [
    "Read",
    "Edit",
    "Write",
    "Glob",
    "Grep",
    "Bash(python *)",
    "Bash(pytest *)",
    "Bash(ruff *)",
    "Bash(npm --prefix frontend *)",
    "Bash(git status*)",
    "Bash(git diff*)",
    "Bash(git log*)",
    "Bash(git add *)",
    "Bash(git commit *)",
]

DISALLOWED_TOOLS = [
    "Bash(git push*)",
    "Bash(git merge*)",
    "Bash(git rebase*)",
    "Bash(gh pr merge*)",
    "Bash(gh pr create*)",
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


def model_command(model: str | None, max_turns: int) -> list[str]:
    """النص يُمرَّر على الدخل القياسي: الخيارات متعددة القيم تبتلع أي وسيط موضعي يليها."""
    cmd = [shutil.which("claude") or "claude", "-p", "--max-turns", str(max_turns)]
    cmd += ["--permission-mode", "acceptEdits"]
    if model:
        cmd += ["--model", model]
    return [*cmd, "--allowedTools", *ALLOWED_TOOLS, "--disallowedTools", *DISALLOWED_TOOLS]


def run_model(path: Path, card: str, model: str | None, max_turns: int) -> int:
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
        env=work_env(card),
    )
    # مخرجات الجلسة الآلية بجوار شجرة العمل (المجلد خارج git) لمراجعة ما فعله النموذج.
    log = WORKTREES / f"{card}.log"
    log.write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")
    return proc.returncode


def unpushable(path: Path) -> str:
    """سبب يمنع الدفع، أو نص فارغ. فرع بلا إيداع يُفشل فتح الطلب، وتعديل غير مودَع يعني عملًا ناقصًا."""
    ahead = sh(
        ["git", "rev-list", "--count", "origin/main..HEAD"], cwd=path, capture_output=True
    ).stdout.strip()
    if not int(ahead or 0):
        return "لا إيداعات فوق origin/main"
    status = sh(["git", "status", "--porcelain"], cwd=path, capture_output=True).stdout.splitlines()
    dirty = [line[3:] for line in status if line[3:] != ".prepush_receipt"]
    if dirty:
        return "تعديلات غير مودَعة: " + "، ".join(dirty[:5])
    return ""


def prepush(path: Path, card: str) -> bool:
    proc = sh(
        [sys.executable, "scripts/prepush_check.py", "--allow-missing"],
        cwd=path,
        check=False,
        env=work_env(card),
    )
    # الإيصال يُكتب في ملف متتبَّع؛ يُعاد كي لا يبقى الفرع متسخًا بعد الفحص.
    sh(["git", "restore", "--", ".prepush_receipt"], cwd=path, check=False)
    return proc.returncode == 0


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


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--max-turns", type=int, default=40)
    args = ap.parse_args(argv)

    card = pick_card()
    if not card:
        print("لا بطاقات ready")
        return 0
    if args.dry_run:
        print(f"سيُلتقط: {card} → worktree .worktrees/{card} → claude → prepush → PR")
        return 0
    if not acquire_lock():
        return 0
    try:
        ledger.append(card, "claimed", pid=os.getpid())
        path, branch = make_worktree(card)
        rc = run_model(path, card, args.model, args.max_turns)
        head = sh(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True).stdout.strip()
        ledger.append(card, "coded", exit_code=rc, head=head)
        if reason := unpushable(path):
            ledger.append(card, "blocked", reason=reason, head=head)
            print(f"لا دفع: {reason} — راجع .worktrees/{card}.log")
            return 1
        if not prepush(path, card):
            ledger.append(card, "prepush_failed", head=head)
            print("الفحص المحلي فشل — البطاقة تبقى في worktree للمراجعة")
            return 1
        ledger.append(card, "prepush_ok", head=head)
        url = push_and_open_pr(path, branch, card)
        ledger.append(card, "pr_opened", url=url, head=head)
        print(f"PR: {url}")
        return 0
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
