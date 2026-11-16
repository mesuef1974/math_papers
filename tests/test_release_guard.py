"""حارس الهجرات في أمر بدء خدمة الويب: لا تبدأ نسخة على قاعدة لم يهاجرها preDeploy."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "railway-release.sh"

# بديل python: يسجّل ما استُدعي به، ويخرج بـ MIGRATE_CHECK_EXIT عند migrate --check.
FAKE_PYTHON = """#!/bin/bash
echo "python $*" >> "$CALLS"
case "$*" in
  *"migrate --check"*) exit "${MIGRATE_CHECK_EXIT:-0}" ;;
esac
exit 0
"""

FAKE_GUNICORN = """#!/bin/bash
echo "gunicorn $*" >> "$CALLS"
exit 0
"""


def _bash() -> str | None:
    """bash حقيقي: على ويندوز bash المرافق لـ git لا System32/bash.exe (مدخل WSL)."""
    if sys.platform != "win32":
        return shutil.which("bash")
    git = shutil.which("git")
    if not git:
        return None
    # git.exe في cmd/ أو mingw64/bin/ بحسب من شغّل الاختبار؛ جذر التثبيت أحد آبائه.
    for base in list(Path(git).resolve().parents)[:4]:
        for candidate in (base / "bin" / "bash.exe", base / "usr" / "bin" / "bash.exe"):
            if candidate.exists():
                return str(candidate)
    return None


def _run(tmp_path: Path, migrate_check_exit: int) -> tuple[int, list[str], str]:
    bash = _bash()
    if bash is None:
        pytest.skip("لا bash على هذا الجهاز")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("python", FAKE_PYTHON), ("gunicorn", FAKE_GUNICORN)):
        fake = bin_dir / name
        fake.write_text(body, encoding="utf-8", newline="\n")
        fake.chmod(0o755)
    calls = tmp_path / "calls.log"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "CALLS": calls.as_posix(),
        "MIGRATE_CHECK_EXIT": str(migrate_check_exit),
    }
    done = subprocess.run(
        [bash, "scripts/railway-release.sh"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=60,
        check=False,
    )
    logged = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
    return done.returncode, logged, done.stderr.decode("utf-8", errors="replace")


def test_release_refuses_to_start_when_migrations_are_unapplied(tmp_path):
    code, calls, stderr = _run(tmp_path, migrate_check_exit=1)

    assert code != 0
    assert calls == ["python manage.py migrate --check --plan"]
    assert "preDeploy" in stderr


def test_release_starts_gunicorn_when_database_is_migrated(tmp_path):
    code, calls, _ = _run(tmp_path, migrate_check_exit=0)

    assert code == 0
    assert calls[0] == "python manage.py migrate --check --plan"
    assert calls[1].startswith("python manage.py collectstatic")
    assert calls[2].startswith("gunicorn config.wsgi:application")
    assert len(calls) == 3


def test_release_script_checks_but_never_migrates():
    text = SCRIPT.read_text(encoding="utf-8")
    commands = [line.strip() for line in text.splitlines() if not line.lstrip().startswith("#")]

    assert text.index("migrate --check") < text.index("exec gunicorn")
    assert not any("manage.py migrate" in c and "--check" not in c for c in commands)
    assert b"\r\n" not in SCRIPT.read_bytes()
