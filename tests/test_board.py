"""لوحة المشغّل: تصنيف البطاقات من الدفتر، وأنها لا تكتب فيه ولا تعرض نصًا خامًا."""

from datetime import UTC, datetime, timedelta

import pytest

from automation import ledger
from scripts import board

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
PR = "https://github.com/o/r/pull/7"


@pytest.fixture
def cards(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER", tmp_path / "ledger")
    monkeypatch.setattr(ledger, "now", lambda: (NOW - timedelta(minutes=5)).isoformat())

    def make(card, *events):
        ledger.append(card, "created", title=f"بطاقة {card}")
        for event in events:
            name, data = event if isinstance(event, tuple) else (event, {})
            ledger.append(card, name, **data)

    return make


def group_of(data: dict) -> dict:
    return {row["id"]: key for key, rows in data["groups"].items() for row in rows}


def test_cards_are_grouped_by_what_needs_attention(tmp_path, cards):
    cards("new")
    cards("queued", "ready")
    cards("live", ("claimed", {"pid": 1}), "coded")
    cards("dead", ("claimed", {"pid": 2}))
    cards("failed", "prepush_failed")
    cards("pr", ("pr_opened", {"url": PR}))
    cards("closed", ("pr_opened", {"url": PR + "8"}))
    cards("done", "merged")
    cards("gone", "cancelled")
    data = board.snapshot(tmp_path, NOW, alive=lambda pid: pid == 1, open_prs={PR})
    assert group_of(data) == {
        "new": "backlog",
        "queued": "queued",
        "live": "running",
        "dead": "stuck",
        "failed": "stuck",
        "pr": "approval",
        "closed": "done",
        "done": "done",
    }
    assert data["groups"]["running"][0]["age"] == "5 د"


def test_without_gh_an_open_pr_card_still_waits_for_the_owner(tmp_path, cards):
    cards("pr", ("pr_opened", {"url": PR}))
    assert group_of(board.snapshot(tmp_path, NOW, open_prs=None)) == {"pr": "approval"}


def test_runner_silence_warns_only_when_nothing_is_running(tmp_path, cards):
    log = tmp_path / ".worktrees" / "runner.log"
    log.parent.mkdir()
    log.write_text(f"{(NOW - timedelta(hours=1)).isoformat()} لا بطاقات ready\n", encoding="utf-8")
    assert board.snapshot(tmp_path, NOW)["pulse"]["warn"]
    cards("live", ("claimed", {"pid": 1}))
    assert not board.snapshot(tmp_path, NOW, alive=lambda pid: True)["pulse"]["warn"]


def test_page_escapes_titles_and_leaves_the_ledger_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER", tmp_path / "ledger")
    ledger.append("x", "created", title="<script>alert(1)</script>")
    ledger.append("x", "ready")
    before = ledger.card_path("x").read_bytes()
    page = board.render(board.snapshot(tmp_path), "")
    assert "<script>" not in page and "&lt;script&gt;" in page
    assert ledger.card_path("x").read_bytes() == before


def test_only_local_host_names_are_served():
    assert board.local_host("127.0.0.1:8791") and board.local_host("localhost:8791")
    assert not board.local_host("evil.example:8791") and not board.local_host(None)
