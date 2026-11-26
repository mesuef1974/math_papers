"""المشغّل المجدوَل: الجلسة الآلية تملك صلاحية الاختبار والإيداع، وما لا يصلح للدفع لا يُدفع، والمهمة مخفية."""

import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pytest

from automation import runner, schedule

CARD = "20260101-abcdef"
HEAD = "a" * 40
NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
TOASTS: list[tuple[str, str]] = []


class Shell:
    """بديل runner.sh: يسجّل الأوامر ويجيب بما ضُبط لكل أمر."""

    def __init__(self, ahead="1", status="", prepush=0, changed="", receipt=None):
        self.calls: list[tuple[list[str], dict]] = []
        self.ahead, self.status, self.prepush, self.changed = ahead, status, prepush, changed
        self.receipt = {"head": HEAD, "checks": {"ruff": "ok", "tests": "ok"}} if receipt is None else receipt

    def __call__(self, cmd, cwd=None, check=True, **kw):
        self.calls.append((cmd, kw))
        out, code = "", 0
        if cmd[:2] == ["git", "rev-list"]:
            out = self.ahead
        elif cmd[:2] == ["git", "status"]:
            out = self.status
        elif cmd[:2] == ["git", "rev-parse"]:
            out = HEAD
        elif cmd[:2] == ["git", "diff"]:
            out = self.changed
        elif cmd[:3] == ["git", "worktree", "add"]:
            Path(cmd[5]).mkdir(parents=True)
        elif cmd[:3] == ["gh", "pr", "create"]:
            out = "https://example.invalid/pull/1"
        elif "scripts/prepush_check.py" in cmd:
            code = self.prepush
            if self.receipt:
                (Path(cwd) / ".prepush_receipt").write_text(json.dumps(self.receipt), encoding="utf-8")
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
    monkeypatch.setattr(runner.sync, "quiet", lambda *_: "")
    monkeypatch.setattr(runner, "HEALTH", tmp_path / ".health")
    monkeypatch.setattr(runner.ledger, "events", lambda card: [d for c, _, d in events if c == card])
    monkeypatch.setattr(
        runner.ledger,
        "state",
        lambda card: next(({"event": e} for c, e, _ in reversed(events) if c == card), None),
    )
    monkeypatch.setattr(runner.notify, "send", lambda title, body: TOASTS.append((title, body)))
    TOASTS.clear()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return events


def names(events) -> list[str]:
    return [event for _, event, _ in events]


def test_model_command_grants_tests_and_commits_but_never_push():
    cmd = runner.model_command("sonnet", 12)
    allowed = cmd[cmd.index("--allowedTools") + 1 : cmd.index("--disallowedTools")]
    denied = cmd[cmd.index("--disallowedTools") + 1 :]
    assert {"Edit", "Bash(python -m pytest *)", "Bash(git add *)", "Bash(git commit *)"} <= set(allowed)
    assert "Bash(python *)" not in allowed, "بايثون مطلق يفتح كل ما حُجب"
    assert not any("git push" in tool or "(gh" in tool or "railway" in tool for tool in allowed)
    assert {"Bash(git push*)", "Bash(gh pr merge*)", "Bash(gh *)", "Bash(railway*)"} <= set(denied)
    assert cmd[1] == "-p" and cmd[cmd.index("--max-turns") + 1] == "12"
    assert cmd[cmd.index("--model") + 1] == "sonnet"


def test_work_env_puts_project_python_first_and_a_test_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env = runner.work_env(CARD)
    assert env["PATH"].split(runner.os.pathsep)[0] == str(Path(runner.sys.executable).parent)
    assert env["DATABASE_URL"].startswith("sqlite:///") and env["DATABASE_URL"].endswith(f"{CARD}.db")
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    assert runner.work_env(CARD)["DATABASE_URL"] == "postgres://x"


def test_model_env_cannot_publish_but_the_runner_env_can(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.quotepath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    env = runner.model_env(CARD)
    assert env["GIT_CONFIG_COUNT"] == "2" and env["GIT_CONFIG_KEY_0"] == "core.quotepath"
    assert (env["GIT_CONFIG_KEY_1"], env["GIT_CONFIG_VALUE_1"]) == (
        "remote.origin.pushurl",
        runner.PUSH_DISABLED,
    )
    assert env["GH_TOKEN"] == env["GITHUB_TOKEN"] == runner.GH_NO_AUTH
    own = runner.work_env(CARD)
    assert "GH_TOKEN" not in own and own["GIT_CONFIG_COUNT"] == "1"


def test_push_disabled_url_really_stops_git_push(tmp_path, monkeypatch):
    """git حقيقي: ببيئة النموذج يفشل الدفع إلى مستودع محلي يقبله ببيئة المشغّل."""
    for name in ("GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"):
        monkeypatch.delenv(name, raising=False)
    remote, work = tmp_path / "remote.git", tmp_path / "work"

    def git(*args, env=None, cwd=work):
        return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)

    git("init", "--bare", str(remote), cwd=tmp_path)
    git("init", str(work), cwd=tmp_path)
    git("remote", "add", "origin", str(remote))
    git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "--allow-empty", "-m", "x")
    assert git("push", "origin", "HEAD:refs/heads/a", env=runner.model_env(CARD)).returncode != 0
    assert git("push", "origin", "HEAD:refs/heads/a", env=runner.work_env(CARD)).returncode == 0


def test_prompt_goes_through_stdin_and_output_is_logged(world, monkeypatch):
    shell = Shell()
    monkeypatch.setattr(runner, "sh", shell)
    assert runner.main([]) == 0
    model_call = next(kw for cmd, kw in shell.calls if "--allowedTools" in cmd)
    assert "عنوان" in model_call["input"] and "DATABASE_URL" in model_call["env"]
    assert model_call["env"]["GH_TOKEN"] == runner.GH_NO_AUTH
    assert (runner.WORKTREES / f"{CARD}.log").exists()


def test_healthy_card_is_pushed_and_recorded(world, monkeypatch):
    shell = Shell()
    monkeypatch.setattr(runner, "sh", shell)
    assert runner.main([]) == 0
    assert names(world) == ["claimed", "coded", "prepush_ok", "pr_opened"]
    assert shell.ran("git", "push")
    assert not runner.LOCK.exists()


def test_branch_without_commits_is_blocked_not_pushed(world, monkeypatch):
    shell = Shell(ahead="0")
    monkeypatch.setattr(runner, "sh", shell)
    assert runner.main([]) == 1
    assert names(world) == ["claimed", "coded", "blocked"]
    assert not shell.ran("git", "push") and not shell.ran("gh", "pr", "create")


def test_uncommitted_work_is_blocked(world, monkeypatch):
    shell = Shell(status=" M apps/core/services.py\n")
    monkeypatch.setattr(runner, "sh", shell)
    assert runner.main([]) == 1
    assert "apps/core/services.py" in world[-1][2]["reason"] and not shell.ran("git", "push")


def test_branch_touching_a_guard_is_blocked_before_the_check_runs(world, monkeypatch):
    shell = Shell(changed="apps/core/services.py\nscripts/prepush_check.py\n")
    monkeypatch.setattr(runner, "sh", shell)
    assert runner.main([]) == 1
    assert names(world)[-1] == "blocked" and "scripts/prepush_check.py" in world[-1][2]["reason"]
    assert not shell.ran("git", "push")
    assert not any("scripts/prepush_check.py" in cmd for cmd, _ in shell.calls)


@pytest.mark.parametrize(
    "path",
    [".github/workflows/quality-gate.yml", ".claude/hooks/guard_git.py", "automation/runner.py"],
)
def test_ci_hooks_and_the_runner_itself_are_guarded(path):
    assert runner.path_forbidden(path, runner.ALWAYS_FORBIDDEN)


def test_runner_check_is_strict_about_missing_tools(world, monkeypatch):
    shell = Shell()
    monkeypatch.setattr(runner, "sh", shell)
    runner.main([])
    check = next(cmd for cmd, _ in shell.calls if "scripts/prepush_check.py" in cmd)
    assert "--allow-missing" not in check
    assert world[-2][1] == "prepush_ok" and world[-2][2]["checks"] == ["ruff", "tests"]


@pytest.mark.parametrize(
    "receipt",
    [
        {},
        {"head": "b" * 40, "checks": {"tests": "ok"}},
        {"head": HEAD, "checks": {"tests": "ok", "secrets": "missing"}},  # pragma: allowlist secret
        {"head": HEAD, "checks": {}},
    ],
    ids=["no-receipt", "other-head", "unmeasured-check", "no-checks"],
)
def test_no_push_without_a_receipt_for_this_head(world, monkeypatch, receipt):
    shell = Shell(receipt=receipt)
    monkeypatch.setattr(runner, "sh", shell)
    assert runner.main([]) == 1
    assert names(world)[-1] == "prepush_failed" and not shell.ran("git", "push")


def test_idle_run_reports_what_the_sync_wrote(world, monkeypatch):
    monkeypatch.setattr(runner, "sh", Shell())
    monkeypatch.setattr(runner.ledger, "cards_in", lambda *_: [])
    monkeypatch.setattr(runner.sync, "quiet", lambda *_: "x → merged (#7)")
    # CI بلا claude على المسار، فالنبض يُلحق «غائب عن المسار»؛ الاختبار عن المزامنة وحدها.
    monkeypatch.setattr(runner.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    assert runner.main([]) == 0
    log = (runner.WORKTREES / "runner.log").read_text(encoding="utf-8").strip()
    assert log.endswith("لا بطاقات ready | مزامنة: x → merged (#7)")


def test_prepush_receipt_stays_out_of_git():
    """الإيصال يتغيّر مع كل فحص؛ لو تُتبِّع لدخل الطلبات وأفشل فحص الأسرار بتجزئة الرأس."""
    root = Path(runner.__file__).resolve().parents[1]
    assert ".prepush_receipt" in (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    tracked = subprocess.run(
        ["git", "ls-files", ".prepush_receipt"], cwd=root, capture_output=True, text=True, check=True
    )
    assert tracked.stdout.strip() == ""


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


def test_guide_extract_python_is_allowed_only_for_the_pipeline_and_its_tests():
    extract = [t for t in runner.ALLOWED_TOOLS if runner.GUIDE_EXTRACT_PYTHON in t]
    assert extract == [
        f"Bash({runner.GUIDE_EXTRACT_PYTHON} -m tools.extraction *)",
        f"Bash({runner.GUIDE_EXTRACT_PYTHON} -m pytest *)",
    ]
    assert not any(t.startswith("Bash(python *") or t == "Bash(python*)" for t in runner.ALLOWED_TOOLS)


def test_the_runner_pins_its_model_unless_told_otherwise(world, tmp_path, monkeypatch):
    for argv, model in (([], runner.DEFAULT_MODEL), (["--model", "opus"], "opus")):
        shell = Shell()
        monkeypatch.setattr(runner, "sh", shell)
        monkeypatch.setattr(runner, "WORKTREES", tmp_path / model)
        assert runner.main(argv) == 0
        cmd = next(cmd for cmd, _ in shell.calls if "--allowedTools" in cmd)
        assert cmd[cmd.index("--model") + 1] == model
        assert cmd[cmd.index("--output-format") + 1] == "json"


def test_usage_sums_every_model_and_keeps_the_text():
    one = {"inputTokens": 1, "outputTokens": 2, "cacheReadInputTokens": 3, "cacheCreationInputTokens": 4}
    out = {"result": "تم", "num_turns": 5, "total_cost_usd": 0.5, "modelUsage": {"b": one, "a": one}}
    text, usage = runner.parse_result(json.dumps(out))
    assert text == "تم"
    assert usage == {
        "input": 2,
        "cache_write": 8,
        "cache_read": 6,
        "output": 4,
        "models": ["a", "b"],
        "turns": 5,
        "cost_usd": 0.5,
    }


@pytest.mark.parametrize("stdout", ["", "Error: x", "[1]", '{"result": "x"}', '{"modelUsage": []}'])
def test_unreadable_output_is_logged_raw_without_usage(stdout):
    assert runner.parse_result(stdout) == (stdout, {})


def dead_lock(monkeypatch, alive=False):
    runner.LOCK.write_text(f"4242 {CARD}", encoding="utf-8")
    monkeypatch.setattr(runner, "process_alive", lambda _: alive)


def test_dead_runner_card_is_recovered_once_then_blocked(world, monkeypatch):
    world.append((CARD, "claimed", {}))
    dead_lock(monkeypatch)
    assert runner.recover().endswith("استُعيدت بعد انقطاع")
    assert world[-1][1] == "ready" and world[-1][2]["retry"] and not runner.LOCK.exists()
    world.append((CARD, "coded", {}))
    dead_lock(monkeypatch)
    runner.recover()
    assert world[-1][1] == "blocked" and runner.failure_streak() == 1


def test_a_living_runner_and_a_manual_claim_are_left_alone(world, monkeypatch):
    world.append((CARD, "claimed", {}))
    assert runner.recover() == "", "بلا قفل: حجز يدوي"
    dead_lock(monkeypatch, alive=True)
    assert runner.recover() == "" and runner.LOCK.exists() and names(world) == ["claimed"]


def test_process_alive_sees_a_child_without_killing_it():
    assert runner.process_alive(runner.os.getpid())
    child = subprocess.Popen([runner.sys.executable, "-c", "input()"], stdin=subprocess.PIPE)
    assert runner.process_alive(child.pid) and child.poll() is None
    child.communicate(b"\n")
    assert not runner.process_alive(child.pid)


def test_model_failure_is_retried_once_without_counting(world, monkeypatch):
    monkeypatch.setattr(runner, "sh", Shell(ahead="0"))
    monkeypatch.setattr(runner, "run_model", lambda *_: (1, {}))
    monkeypatch.setattr(runner, "make_worktree", lambda card: (runner.WORKTREES, f"card/{card}"))
    assert runner.main([]) == 1
    assert names(world) == ["claimed", "coded", "ready"] and not TOASTS
    assert runner.main([]) == 1
    assert names(world)[-1] == "blocked" and runner.failure_streak() == 1 and len(TOASTS) == 1


def test_two_failures_halt_the_runner_until_resumed(world, monkeypatch):
    shell = Shell(prepush=1)
    monkeypatch.setattr(runner, "sh", shell)
    monkeypatch.setattr(runner, "make_worktree", lambda card: (runner.WORKTREES, f"card/{card}"))
    runner.WORKTREES.mkdir()
    assert runner.main([]) == 1 and runner.main([]) == 1
    assert TOASTS[-1][0] == "المشغّل توقف"
    calls = len(shell.calls)
    assert runner.main([]) == 0 and len(shell.calls) == calls
    assert runner.main(["--resume"]) == 0 and runner.failure_streak() == 0
    assert runner.main([]) == 1 and len(shell.calls) > calls


def test_a_success_clears_the_streak_and_notifies(world, monkeypatch):
    monkeypatch.setattr(runner, "sh", Shell())
    runner.HEALTH.write_text('{"streak": 1}', encoding="utf-8")
    assert runner.main([]) == 0
    assert runner.failure_streak() == 0 and TOASTS[0][0] == "المشغّل: طلب جاهز للمراجعة"
