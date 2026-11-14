"""بوابة الدمج الآلي: تحكم بآخر تشغيل لكل فحص، وتستثني حالة نافذة النشر، وتمنع المسارات المحظورة."""

from scripts import merge_gate as mg
from scripts.approval import approval_line

HEAD = "1ef42574e2aa00000000000000000000000000aa"


def run(name, conclusion, started, workflow="بوابة الجودة", status="COMPLETED"):
    return {
        "name": name,
        "workflowName": workflow,
        "status": status,
        "conclusion": conclusion,
        "startedAt": started,
    }


APPROVAL_OLD = run("approval-head", "FAILURE", "2026-11-14T04:41:32Z", "سطر الاعتماد يطابق الرأس")
APPROVAL_NEW = run("approval-head", "SUCCESS", "2026-11-14T04:46:03Z", "سطر الاعتماد يطابق الرأس")
GREEN = [
    run("ruff + format + secrets", "SUCCESS", "2026-11-14T04:41:32Z"),
    run("نافذة النشر (في طابور الدمج فقط)", "SKIPPED", "2026-11-14T04:41:31Z"),
    run("بوابة الجودة", "SUCCESS", "2026-11-14T04:45:28Z"),
]


def test_superseded_failed_run_is_not_counted():
    # ترتيب GitHub كما ورد في الطلب 22: القديم الفاشل ثم الجديد الناجح، وبينهما فحوص أخرى.
    assert mg.check_reasons([APPROVAL_OLD, *GREEN, APPROVAL_NEW]) == []
    assert mg.check_reasons([APPROVAL_NEW, *GREEN, APPROVAL_OLD]) == []  # الحكم بالوقت لا بالترتيب


def test_latest_run_decides_when_it_fails_or_is_pending():
    newer_failure = {**APPROVAL_OLD, "startedAt": "2026-11-14T05:00:00Z"}
    assert mg.check_reasons([APPROVAL_NEW, *GREEN, newer_failure]) == ["فحص فاشل: approval-head"]
    rerun = run("بوابة الجودة", "", "2026-11-14T05:00:00Z", status="IN_PROGRESS")
    assert mg.check_reasons([APPROVAL_NEW, *GREEN, rerun]) == ["فحص لم يكتمل: بوابة الجودة"]
    assert mg.check_reasons([]) == ["لا فحوص CI مسجّلة على الطلب بعد"]


def test_same_job_name_in_two_workflows_is_two_checks():
    other = run("بوابة الجودة", "FAILURE", "2026-11-14T04:00:00Z", workflow="سير آخر")
    assert mg.check_reasons([*GREEN, other]) == ["فحص فاشل: بوابة الجودة"]


def test_deploy_window_status_does_not_block_enabling_auto_merge():
    window = {"context": mg.DEPLOY_WINDOW, "state": "FAILURE", "startedAt": "2026-11-15T04:00:00Z"}
    assert mg.check_reasons([APPROVAL_NEW, *GREEN, window]) == []
    other = {"context": "فحص خارجي", "state": "PENDING", "startedAt": "2026-11-15T04:00:00Z"}
    assert mg.check_reasons([APPROVAL_NEW, *GREEN, other]) == ["فحص لم يكتمل: فحص خارجي"]


def pr(body, files, checks):
    return {
        "headRefOid": HEAD,
        "body": body,
        "files": [{"path": p} for p in files],
        "statusCheckRollup": checks,
    }


def test_evaluate_allows_an_approved_green_pr(monkeypatch):
    body = "وصف\n\n" + approval_line("2026-11-14", HEAD)
    checks = [APPROVAL_OLD, *GREEN, APPROVAL_NEW]
    monkeypatch.setattr(mg, "gh_json", lambda args: pr(body, ["apps/papers/word/ooxml.py"], checks))
    assert mg.evaluate("22", "o/r") == (True, [])


def test_evaluate_keeps_guard_files_and_unapproved_heads_manual(monkeypatch):
    checks = [*GREEN, APPROVAL_NEW]
    stale = "وصف\n\n" + approval_line("2026-11-14", "0" * 40)
    monkeypatch.setattr(mg, "gh_json", lambda args: pr(stale, ["scripts/merge_gate.py"], checks))
    ok, reasons = mg.evaluate("22", None)
    assert ok is False and len(reasons) == 2
    assert "رأس قديم" in reasons[0] and "scripts/merge_gate.py" in reasons[1]
    monkeypatch.setattr(
        mg, "gh_json", lambda args: pr("بلا اعتماد", [".github/workflows/deploy-window.yml"], checks)
    )
    ok, reasons = mg.evaluate("22", None)
    assert ok is False and "لا سطر اعتماد" in reasons[0] and ".github" in reasons[1]


def test_enable_merges_by_squash_only_when_allowed(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(mg.subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(mg.sys, "argv", ["merge_gate.py", "22", "--repo", "o/r", "--enable"])
    monkeypatch.setattr(mg, "evaluate", lambda number, repo: (True, []))
    assert mg.main() == 0
    assert calls == [["gh", "pr", "merge", "22", "--auto", "--squash", "--repo", "o/r"]]
    calls.clear()
    monkeypatch.setattr(mg, "evaluate", lambda number, repo: (False, ["فحص فاشل: x"]))
    assert mg.main() == 1 and calls == []
    assert "يبقى دمجًا يدويًا" in capsys.readouterr().out
