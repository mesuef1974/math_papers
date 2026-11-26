"""مزامنة الدفتر: الحدث من حالة الطلب على GitHub، والمغلق بلا دمج لا يُكتب، والعطل لا يوقف المشغّل."""

import pytest

from automation import sync

ledger = sync.ledger  # الوحدة التي تقرؤها المزامنة نفسها

CARD = "20260101-abcdef"


def pr(number, state, branch=f"card/{CARD}", merged_at=None):
    return {
        "number": number,
        "state": state,
        "url": f"https://example.invalid/pull/{number}",
        "headRefName": branch,
        "mergedAt": merged_at,
    }


@pytest.fixture(autouse=True)
def book(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER", tmp_path / "ledger")


def card_in(state: str, card: str = CARD) -> str:
    ledger.append(card, "created", title="عنوان", body="وصف")
    ledger.append(card, state)
    return card


def test_merged_pr_writes_merged_with_its_number():
    card_in("pr_opened")
    assert sync.apply(sync.plan([pr(7, "MERGED", merged_at="2026-11-18T10:00:00Z")])) == [
        f"{CARD} → merged (#7)"
    ]
    last = ledger.state(CARD)
    assert (last["event"], last["pr"], last["note"]) == ("merged", 7, "sync")


def test_open_pr_is_recorded_only_for_a_card_that_never_recorded_it():
    assert sync.decide("prepush_ok", [pr(3, "OPEN")])[0] == "pr_opened"
    assert sync.decide("pr_opened", [pr(3, "OPEN")])[0] is None
    assert sync.decide("approved", [pr(3, "OPEN")])[0] is None


def test_closed_unmerged_pr_writes_nothing_but_is_shown():
    event, shown = sync.decide("pr_opened", [pr(4, "CLOSED")])
    assert event is None and shown["number"] == 4


def test_a_reopened_branch_follows_its_merged_pr():
    event, shown = sync.decide(
        "pr_opened", [pr(4, "CLOSED"), pr(5, "MERGED", merged_at="2026-11-18T10:00:00Z")]
    )
    assert (event, shown["number"]) == ("merged", 5)


def test_card_without_a_pr_and_finished_cards_are_left_alone():
    card_in("prepush_ok")
    card_in("merged", "20260102-bbbbbb")
    rows = sync.plan([pr(9, "MERGED", branch="card/20260102-bbbbbb"), pr(8, "MERGED", branch="other")])
    assert rows == [(CARD, None, None)]
    assert sync.apply(rows) == [] and ledger.state(CARD)["event"] == "prepush_ok"


def test_sync_is_idempotent():
    card_in("pr_opened")
    prs = [pr(7, "MERGED", merged_at="2026-11-18T10:00:00Z")]
    sync.apply(sync.plan(prs))
    assert sync.apply(sync.plan(prs)) == []
    assert [e["event"] for e in ledger.events(CARD)] == ["created", "pr_opened", "merged"]


def test_quiet_never_calls_gh_without_pending_cards(monkeypatch):
    card_in("deployed")
    monkeypatch.setattr(sync, "fetch_prs", lambda _: pytest.fail("gh استُدعي بلا بطاقة معلّقة"))
    assert sync.quiet() == ""


def test_quiet_reports_a_failure_instead_of_raising(monkeypatch):
    card_in("pr_opened")

    def broken(_):
        raise RuntimeError("gh فشل")

    monkeypatch.setattr(sync, "fetch_prs", broken)
    assert sync.quiet() == "تعذّرت (RuntimeError)"
    assert ledger.state(CARD)["event"] == "pr_opened"


def test_finished_worktrees_lists_only_done_cards():
    card_in("merged")
    card_in("pr_opened", "20260102-bbbbbb")
    porcelain = (
        "worktree D:/p\nHEAD aaa\nbranch refs/heads/main\n\n"
        f"worktree D:/p/.worktrees/{CARD}\nHEAD bbb\nbranch refs/heads/card/{CARD}\n\n"
        "worktree D:/p/.worktrees/20260102-bbbbbb\nHEAD ccc\nbranch refs/heads/card/20260102-bbbbbb\n\n"
        "worktree D:/p/.worktrees/x\nHEAD ddd\ndetached\n"
    )
    assert sync.finished_worktrees(porcelain) == [(f"D:/p/.worktrees/{CARD}", f"card/{CARD}", "merged")]


@pytest.mark.parametrize(
    ("states", "event"),
    [({"success", "in_progress"}, "deployed"), ({"failure"}, "blocked"), (set(), "merged")],
)
def test_a_merged_card_follows_its_deployment(book, monkeypatch, states, event):
    card_in("merged")
    toasts = []
    monkeypatch.setattr(sync, "deploy_states", lambda sha, repo: states)
    monkeypatch.setattr(sync.notify, "send", lambda *args: toasts.append(args))
    prs = [pr(7, "MERGED") | {"mergeCommit": {"oid": "a" * 40}}]
    sync.apply_deploys(sync.awaiting_deploy(), prs, None)
    assert ledger.state(CARD)["event"] == event
    assert len(toasts) == (event == "blocked")


def test_old_merges_are_not_asked_about(book):
    card_in("merged")
    later = sync.datetime.now(sync.UTC) + sync.DEPLOY_WINDOW * 2
    assert sync.awaiting_deploy() == [CARD] and sync.awaiting_deploy(later) == []
