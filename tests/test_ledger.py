"""دفتر البطاقات: الأحداث تُضاف ولا تُحرَّر، والحالة آخر حدث، وlist يصفّي بالحالة."""

import json
import re

import pytest

from automation import ledger

CARD = "20260101-abcdef"


@pytest.fixture(autouse=True)
def book(tmp_path, monkeypatch):
    """دفتر في مجلد مؤقت لم يُنشأ بعد: دفتر المشروع لا يُمسّ."""
    path = tmp_path / "ledger"
    monkeypatch.setattr(ledger, "LEDGER", path)
    return path


def rows(book, card_id):
    return [json.loads(line) for line in (book / f"{card_id}.jsonl").read_text(encoding="utf-8").splitlines()]


def test_new_card_writes_created_event(book):
    cid = ledger.new_card("عنوان", "وصف", "شرط النجاح")

    assert re.fullmatch(r"\d{8}-[0-9a-f]{6}", cid)
    (row,) = rows(book, cid)
    assert row["card"] == cid
    assert row["event"] == "created"
    assert (row["title"], row["body"], row["success"]) == ("عنوان", "وصف", "شرط النجاح")
    assert row["at"]


def test_new_card_ids_are_distinct():
    assert ledger.new_card("أ", "ب") != ledger.new_card("أ", "ب")


def test_append_adds_a_line_and_keeps_earlier_ones(book):
    ledger.append(CARD, "created", title="عنوان")
    row = ledger.append(CARD, "ready", note="ملاحظة")

    assert row["event"] == "ready"
    assert row["note"] == "ملاحظة"
    assert [r["event"] for r in rows(book, CARD)] == ["created", "ready"]
    assert rows(book, CARD)[1] == row


def test_append_keeps_arabic_readable_in_the_file(book):
    ledger.append(CARD, "created", title="عنوان")

    assert "عنوان" in (book / f"{CARD}.jsonl").read_text(encoding="utf-8")


def test_append_rejects_unknown_event(book):
    with pytest.raises(ValueError, match="حدث غير معروف"):
        ledger.append(CARD, "done")

    assert not book.exists()


def test_state_is_the_last_event():
    ledger.append(CARD, "created")
    ledger.append(CARD, "ready")
    ledger.append(CARD, "claimed")

    assert ledger.state(CARD)["event"] == "claimed"
    assert ledger.first(CARD)["event"] == "created"


def test_state_of_missing_card_is_none():
    assert ledger.state(CARD) is None


def test_cards_in_filters_by_current_state():
    ledger.append("20260101-aaaaaa", "created")
    ledger.append("20260101-bbbbbb", "created")
    ledger.append("20260101-bbbbbb", "ready")
    ledger.append("20260101-cccccc", "created")
    ledger.append("20260101-cccccc", "ready")
    ledger.append("20260101-cccccc", "claimed")

    assert ledger.cards_in("ready") == ["20260101-bbbbbb"]
    assert ledger.cards_in("created", "claimed") == ["20260101-aaaaaa", "20260101-cccccc"]
    assert ledger.cards_in("merged") == []


def test_cards_in_without_ledger_dir_is_empty():
    assert ledger.cards_in("ready") == []


def seed_two_cards():
    ledger.append("20260101-aaaaaa", "created", title="الأولى")
    ledger.append("20260101-bbbbbb", "created", title="الثانية")
    ledger.append("20260101-bbbbbb", "ready")


def test_list_without_state_prints_every_card(capsys):
    seed_two_cards()

    assert ledger.main(["list"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[:2] for line in lines] == [
        ["20260101-aaaaaa", "created"],
        ["20260101-bbbbbb", "ready"],
    ]
    assert lines[1].endswith("الثانية")


def test_list_state_prints_only_cards_in_that_state(capsys):
    seed_two_cards()

    assert ledger.main(["list", "--state", "ready"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[:2] for line in lines] == [["20260101-bbbbbb", "ready"]]


def test_list_state_with_no_match_prints_nothing(capsys):
    seed_two_cards()

    assert ledger.main(["list", "--state", "merged"]) == 0

    assert capsys.readouterr().out == ""


def test_list_rejects_state_outside_states(capsys):
    with pytest.raises(SystemExit) as exc:
        ledger.main(["list", "--state", "done"])

    assert exc.value.code == 2
