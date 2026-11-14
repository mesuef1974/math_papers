"""نافذة النشر: حالة الإيداع المطلوبة التي تفرض النافذة بلا طابور دمج، وجدولة سير العمل الذي يحدّثها."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts import deploy_window as dw

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy-window.yml"


def local(day: int, hour: int, minute: int = 0) -> datetime:
    """وقت محلي (UTC+3) في نوفمبر 2026: 12 خميس، 13 جمعة، 14 سبت، 15 أحد."""
    return datetime(2026, 11, day, hour, minute, tzinfo=dw.LOCAL_TZ).astimezone(UTC)


@pytest.mark.parametrize(
    ("moment", "state"),
    [
        (local(15, 6, 29), "success"),  # قبل الاحتياط
        (local(15, 6, 30), "failure"),  # الاحتياط: نصف ساعة قبل الدوام
        (local(15, 7, 0), "failure"),
        (local(12, 13, 59), "failure"),
        (local(12, 14, 0), "success"),  # انتهى الدوام
        (local(13, 10, 0), "success"),  # الجمعة
        (local(14, 10, 0), "success"),  # السبت
        (local(14, 23, 45), "success"),  # ليلة الأحد: الاحتياط لا يغلق قبل 06:30
    ],
)
def test_status_follows_work_hours_with_guard(moment, state):
    assert dw.status_for(moment, [])[0] == state


def test_urgent_label_opens_the_window():
    state, description = dw.status_for(local(15, 10, 0), ["توثيق", dw.LABEL])
    assert state == "success" and dw.LABEL in description
    assert dw.status_for(local(15, 10, 0), ["توثيق"])[0] == "failure"


def test_descriptions_fit_a_commit_status():
    for moment in (local(15, 10, 0), local(14, 10, 0)):
        for labels in ([], [dw.LABEL]):
            assert len(dw.status_for(moment, labels)[1]) <= 140


def test_every_open_pr_gets_its_status(monkeypatch):
    prs = [
        {"number": 7, "sha": "a" * 40, "labels": []},
        {"number": 9, "sha": "b" * 40, "labels": [dw.LABEL]},
    ]
    posted = []
    monkeypatch.setattr(dw, "open_prs", lambda repo, base: prs if (repo, base) == ("o/r", "main") else [])
    monkeypatch.setattr(dw, "post_status", lambda repo, sha, state, description: posted.append((sha, state)))
    assert dw.update_statuses("o/r", "main", local(15, 10, 0)) == [(7, "failure"), (9, "success")]
    assert posted == [("a" * 40, "failure"), ("b" * 40, "success")]
    posted.clear()
    assert dw.update_statuses("o/r", "main", local(15, 15, 0)) == [(7, "success"), (9, "success")]


def test_merge_queue_mode_is_unchanged():
    assert dw.decide("merge_group", local(15, 10, 0), [])[0] is False
    assert dw.decide("merge_group", local(15, 10, 0), [dw.LABEL])[0] is True
    assert dw.decide("pull_request", local(15, 10, 0), [])[0] is True


def test_schedule_closes_before_work_and_opens_after_it():
    text = WORKFLOW.read_text(encoding="utf-8")
    crons = re.findall(r'cron: "([\d,]+) (\d+) \* \* ([\d-]+)"', text)
    assert len(crons) == 2 and all(days == "0-4" for _, _, days in crons)  # الأحد إلى الخميس بتوقيت UTC
    runs = [(int(hour), int(minute)) for minutes, hour, _ in crons for minute in minutes.split(",")]
    sunday = datetime(2026, 11, 15, tzinfo=UTC)
    states = {
        (hour, minute): dw.status_for(sunday + timedelta(hours=hour, minutes=minute), [])[0]
        for hour, minute in runs
    }
    closing = [state for (hour, _), state in states.items() if hour < 7]
    opening = [state for (hour, _), state in states.items() if hour >= 7]
    assert len(closing) >= 3 and set(closing) == {"failure"}  # كل محاولات الصباح تغلق، وقبل 07:00 المحلية
    assert all((hour + 3, minute) < (7, 0) for hour, minute in states if hour < 7)
    assert len(opening) >= 2 and set(opening) == {"success"}
    assert "scripts/deploy_window.py status" in text and "statuses: write" in text
    assert f"name: {dw.STATUS_CONTEXT}" in text
