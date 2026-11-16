"""المشغّل المجدوَل: الجلسة الآلية تملك صلاحية الاختبار والإيداع، وما لا يصلح للدفع لا يُدفع، والمهمة مخفية."""

import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pytest

from automation import runner, schedule

CARD = "20260101-abcdef"
NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


class Shell:
    """بديل runner.sh: يسجّل الأوامر ويجيب بما ضُبط لكل أمر."""

    def __init__(self, ahead="1", status="", prepush=0):
        self.calls: list[tuple[list[str], dict]] = []
        self.ahead, self.status, self.prepush = ahead, status, prepush

    def __call__(self, cmd, cwd=None, check=True, **kw):
        self.calls.append((cmd, kw))
        out, code = "", 0
        if cmd[:2] == ["git", "rev-list"]:
            out = self.ahead
        elif cmd[:2] == ["git", "status"]:
            out = self.status
        elif cmd[:2] == ["git", "rev-parse"]:
            out = "a" * 40
        elif cmd[:3] == ["gh", "pr", "create"]:
            out = "https://example.invalid/pull/1"
        elif "scripts/prepush_check.py" in cmd:
            code = self.prepush
        return subprocess.CompletedProcess(cmd, code, stdout=out, stderr="")

    def ran(self, *prefix: str) -> bool:
        return any(cmd[: len(prefix)] == list(prefix) for cmd, _ in self.calls)


@pytest.fixture
def world(tmp_path, monkeypatch):
    """دفتر وأشجار عمل وقفل في مجلد مؤقت، وبطاقة ready واحدة."""
    events: list[tuple[str, str, dict]] = []
    monkeypatch.setattr(runner, "WORKTREES", tmp_path / ".worktrees")
    monkeypatch.setattr(runner, "LOCK", tmp_path / ".lock")
    monkeypatch.setattr(runner.ledger, "cards_in", lambda *_: [CARD])
    monkeypatch.setattr(
        runner.ledger, "first", lambda _: {"title": "عنوان", "body": "وصف", "success": "اختبار"}
    )
    monkeypatch.setattr(
        runner.ledger, "append", lambda card, event, **data: events.append((card, event, data))
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return events


def names(events) -> list[str]:
    return [event for _, event, _ in events]


def test_model_command_grants_tests_and_commits_but_never_push():
    cmd = runner.model_command("sonnet", 12)
    allowed = cmd[cmd.index("--allowedTools") + 1 : cmd.index("--disallowedTools")]
    denied = cmd[cmd.index("--disallowedTools") + 1 :]
    assert {"Edit", "Bash(python *)", "Bash(git add *)", "Bash(git commit *)"} <= set(allowed)
    assert not any("push" in tool or "gh pr" in tool or "railway" in tool for tool in allowed)
    assert {"Bash(git push*)", "Bash(gh pr merge*)", "Bash(railway*)"} <= set(denied)
    assert cmd[1] == "-p" and cmd[cmd.index("--max-turns") + 1] == "12"
    assert cmd[cmd.index("--model") + 1] == "sonnet"


def test_work_env_puts_project_python_first_and_a_test_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env = runner.work_env(CARD)
    assert env["PATH"].split(runner.os.pathsep)[0] == str(Path(runner.sys.executable).parent)
    assert env["DATABASE_URL"].startswith("sqlite:///") and env["DATABASE_URL"].endswith(f"{CARD}.db")
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    assert runner.work_env(CARD)["DATABASE_URL"] == "postgres://x"


def test_prompt_goes_through_stdin_and_output_is_logged(world, monkeypatch):
    shell = Shell()
    monkeypatch.setattr(runner, "sh", shell)
    assert runner.main([]) == 0
    model_call = next(kw for cmd, kw in shell.calls if "--allowedTools" in cmd)
    assert "عنوان" in model_call["input"] and "DATABASE_URL" in model_call["env"]
    assert (runner.WORKTREES / f"{CARD}.log").exists()


def test_healthy_card_is_pushed_and_recorded(world, monkeypatch):
    shell = Shell()
    monkeypatch.setattr(runner, "sh", shell)
    assert runner.main([]) == 0
    assert names(world) == ["claimed", "coded", "prepush_ok", "pr_opened"]
    assert shell.ran("git", "push") and shell.ran("git", "restore", "--", ".prepush_receipt")
    assert not runner.LOCK.exists()


def test_branch_without_commits_is_blocked_not_pushed(world, monkeypatch):
    shell = Shell(ahead="0")
    monkeypatch.setattr(runner, "sh", shell)
    assert runner.main([]) == 1
    assert names(world) == ["claimed", "coded", "blocked"]
    assert not shell.ran("git", "push") and not shell.ran("gh", "pr", "create")


def test_uncommitted_work_is_blocked_but_the_receipt_alone_is_not(world, monkeypatch):
    shell = Shell(status=" M apps/core/services.py\n M .prepush_receipt\n")
    monkeypatch.setattr(runner, "sh", shell)
    assert runner.main([]) == 1
    assert "apps/core/services.py" in world[-1][2]["reason"] and not shell.ran("git", "push")

    world.clear()
    receipt_only = Shell(status=" M .prepush_receipt\n")
    monkeypatch.setattr(runner, "sh", receipt_only)
    assert runner.main([]) == 0 and receipt_only.ran("git", "push")


def test_failed_prepush_is_not_pushed(world, monkeypatch):
    shell = Shell(prepush=1)
    monkeypatch.setattr(runner, "sh", shell)
    assert runner.main([]) == 1
    assert names(world)[-1] == "prepush_failed" and not shell.ran("git", "push")


def test_no_ready_card_never_calls_the_model(world, monkeypatch):
    shell = Shell()
    monkeypatch.setattr(runner, "sh", shell)
    monkeypatch.setattr(runner.ledger, "cards_in", lambda *_: [])
    assert runner.main([]) == 0
    assert shell.calls == [] and world == []


def test_every_run_leaves_a_heartbeat_naming_missing_tools(world, monkeypatch):
    monkeypatch.setattr(runner, "sh", Shell())
    monkeypatch.setattr(runner.ledger, "cards_in", lambda *_: [])
    monkeypatch.setattr(runner.shutil, "which", lambda tool: None if tool == "gh" else tool)
    monkeypatch.setattr(runner, "HEARTBEAT_KEEP", 3)
    for _ in range(5):
        assert runner.main([]) == 0
    lines = (runner.WORKTREES / "runner.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert "لا بطاقات ready" in lines[-1] and lines[-1].endswith("غائب عن المسار: gh")


def test_dry_run_leaves_no_heartbeat(world, monkeypatch):
    monkeypatch.setattr(runner, "sh", Shell())
    assert runner.main(["--dry-run"]) == 0
    assert world == [] and not (runner.WORKTREES / "runner.log").exists()


def test_scheduled_task_is_hidden_headless_and_single_instance():
    python = Path(r"D:\مشروع بمسافة\.venv\Scripts\python.exe")
    root = Path(r"D:\مشروع بمسافة")
    xml = schedule.task_xml(python, root, 5, datetime(2026, 11, 16, 9, 30), r"PC\user", "sonnet")
    task = ET.fromstring(xml.split("?>", 1)[1])
    assert task.findtext("t:Settings/t:Hidden", namespaces=NS) == "true"
    assert task.findtext("t:Settings/t:MultipleInstancesPolicy", namespaces=NS) == "IgnoreNew"
    assert task.findtext("t:Triggers/t:TimeTrigger/t:Repetition/t:Interval", namespaces=NS) == "PT5M"
    assert task.findtext("t:Actions/t:Exec/t:Command", namespaces=NS).endswith("conhost.exe")
    arguments = task.findtext("t:Actions/t:Exec/t:Arguments", namespaces=NS)
    assert arguments.startswith(f'--headless "{python}" "{root}')
    assert arguments.endswith('runner.py" --once --model sonnet')
