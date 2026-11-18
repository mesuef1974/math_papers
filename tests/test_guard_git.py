"""حارس git: كل دفع من الجلسة محجوب إلا بإذن المالك المكتوب في التجاوز، وما ليس دفعًا يمرّ."""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("guard_git", ROOT / ".claude" / "hooks" / "guard_git.py")
guard = importlib.util.module_from_spec(SPEC)
sys.modules["guard_git"] = guard
SPEC.loader.exec_module(guard)


def rules(command: str, tool: str = "Bash", branch: str = "card/x") -> list[str]:
    result = guard.check(
        command,
        tool=tool,
        cwd=str(ROOT),
        project_dir=str(ROOT),
        alias_lookup=lambda _: None,
        branch_lookup=lambda _: branch,
    )
    return [hit.rule for hit in result.hits]


@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git push -u origin card/20261118-d11540",
        "git push origin HEAD:refs/heads/card/x",
        "git -C .worktrees/x push origin card/x",
        "bash -c 'git push origin card/x'",
        "cd .worktrees/x && git push -u origin card/x",
    ],
)
def test_every_push_is_blocked(command):
    assert "push-any" in rules(command)


def test_powershell_push_is_blocked():
    assert "push-any" in rules("git push -u origin card/x", tool="PowerShell")


@pytest.mark.parametrize(
    "command",
    [
        "git push --dry-run origin card/x",
        "git push -n origin card/x",
        "git fetch origin main",
        "git commit -m 'git push origin main'",
        "git status --porcelain",
    ],
)
def test_what_publishes_nothing_passes(command):
    assert rules(command) == []


def test_push_to_main_still_names_its_own_rule():
    assert {"push-any", "push-main"} <= set(rules("git push origin main"))


def test_push_in_a_foreign_repository_is_not_ours_to_block(tmp_path):
    assert "push-any" not in rules(f'git -C "{tmp_path.as_posix()}" push origin card/x')


def run_hook(command: str, monkeypatch, capsys) -> int:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(ROOT)}
    stdin = io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode("utf-8")), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(ROOT))
    monkeypatch.setattr(guard, "_log_override", lambda *_: None)
    return guard.main()


def test_hook_blocks_a_plain_branch_push_with_exit_2(monkeypatch, capsys):
    assert run_hook("git push -u origin card/x", monkeypatch, capsys) == 2
    assert "push-any" in capsys.readouterr().err


def test_owner_permission_in_the_override_lets_the_push_through(monkeypatch, capsys):
    command = "GUARD_GIT_ALLOW='إذن المالك بدفع الفرع 2026-11-18' git push -u origin card/x"
    assert run_hook(command, monkeypatch, capsys) == 0


def test_a_short_override_is_not_a_permission(monkeypatch, capsys):
    assert run_hook("GUARD_GIT_ALLOW='ok' git push -u origin card/x", monkeypatch, capsys) == 2
