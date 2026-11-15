from tools.extraction import layout
from tools.extraction.text import squash

from .conftest import TOY_PAGES, make_book


def sq(pages):
    return {n: squash(t) for n, t in pages.items()}


def test_lessons_by_opener_with_stop_marker(toy):
    ls = layout.lessons(sq(TOY_PAGES), toy)
    assert [(r["opener"], r["end"]) for r in ls] == [(2, 5), (6, 8)]
    assert ls[0]["ended_by"] == "next"
    assert ls[1]["ended_by"] == "stop"  # مراجعة الوحدة في ص9 توقف الدرس الثاني عند ص8


def test_printed_ids_win_when_unique_and_ascending(toy):
    ls = layout.lessons(sq(TOY_PAGES), toy)
    assert [(r["id"], r["id_source"], r["unit"]) for r in ls] == [("1.1", "guide", 1), ("1.2", "guide", 1)]


def test_derived_ids_when_no_printed_pattern(tmp_path):
    book = make_book(tmp_path, TOY_PAGES)
    ls = layout.lessons(sq(TOY_PAGES), book)
    assert [(r["id"], r["id_source"]) for r in ls] == [("1.1", "derived"), ("1.2", "derived")]


def test_unit_gap_starts_new_unit(tmp_path):
    pages = {
        1: "ما ستتعلمه 12A.1.1",
        2: "x",
        3: "ما ستتعلمه 12A.1.2",
        4: "مراجعة الوحدة",
        20: "ما ستتعلمه 12A.2.1",
        21: "x",
    }
    book = make_book(tmp_path, pages, layout={"unit_gap": 5, "max_span": 30})
    ls = layout.lessons(sq(pages), book)
    assert [r["id"] for r in ls] == ["1.1", "1.2", "2.1"]


def test_build_checks_and_status(toy):
    first, second = layout.build(toy)["lessons"]
    assert first["status"] == "ok" and second["status"] == "ok"
    assert all(first["checks"].values())
    assert first["source"] == "derived"


def test_build_flags_review_on_overlong_or_missing_standard(tmp_path):
    pages = {1: "ما ستتعلمه معايير الدرس", 2: "x", 3: "x", 4: "x"}
    book = make_book(tmp_path, pages, layout={"max_span": 3})
    rec = layout.build(book)["lessons"][0]
    assert rec["status"] == "review"
    assert rec["checks"]["length_ok"] is False
    assert rec["checks"]["standard_found"] is False


def test_opener_needs_standard_filters_running_text(tmp_path):
    pages = {1: "ما ستتعلمه 12A.1.1", 2: "في نص جاري كلمة ما ستتعلمه فقط", 3: "x"}
    book = make_book(tmp_path, pages, layout={"opener_needs_standard": True})
    assert layout.openers(sq(pages), book) == [1]


def test_page_types(toy):
    types = layout.build(toy)["pages"]
    assert types[1]["type"] == "pre_lesson"
    assert (types[2]["type"], types[2]["status"]) == ("lesson_opener", "ok")
    assert types[3]["type"] == "lesson_body"
    assert types[9]["type"] == "post_lesson" and types[9]["status"] == "review"
    assert "end_stop" in types[9]["hints"]


def test_page_types_between_units(tmp_path):
    pages = {1: "ما ستتعلمه 12A.1.1", 2: "x", 3: "مراجعة الوحدة", 4: "x", 5: "ما ستتعلمه 12A.2.1", 6: "x"}
    book = make_book(tmp_path, pages, layout={"unit_gap": 1})
    types = layout.build(book)["pages"]
    assert types[3]["type"] == "unit_gap"
    assert "end_stop" in types[3]["hints"]


def _analysis_book(tmp_path, pages):
    return make_book(
        tmp_path,
        pages,
        markers={"opener": "نظرة عامة على الدرس", "analysis": "تحليل التمارين", "quiz": "المعيار"},
        standards={"pattern": r"10\.\d+\.\d+"},
        layout={"anchor": "analysis", "end": "quiz", "opener_window": [2, 5], "quiz_window": 3},
    )


def test_analysis_anchor_with_quiz(tmp_path):
    pages = dict.fromkeys(range(1, 15), "x")
    pages |= {1: "نظرة عامة على الدرس هدف", 4: "جدول تحليل التمارين", 5: "المعيار 10.1.1"}
    pages |= {10: "نظرة عامة على الدرس هدف", 13: "جدول تحليل التمارين", 14: "المعيار 10.1.2"}
    book = _analysis_book(tmp_path, pages)
    ls = layout.lessons(sq(pages), book)
    assert [(r["opener"], r["table"], r["quiz"]) for r in ls] == [(1, 4, 5), (10, 13, 14)]
    types = layout.build(book)["pages"]
    assert types[4]["type"] == "analysis_table" and types[5]["type"] == "lesson_quiz"


def test_standard_checked_on_quiz_page_when_configured(tmp_path):
    pages = dict.fromkeys(range(1, 8), "x")
    pages |= {1: "نظرة عامة على الدرس هدف", 4: "دليل المهام", 5: "المعيار 10.1.1"}
    book = _analysis_book(tmp_path, pages)
    book.cfg["layout"]["standard_on"] = "quiz"
    book.cfg["markers"]["analysis"] = "دليل المهام"
    assert layout.build(book)["lessons"][0]["checks"]["standard_found"] is True
    book.cfg["layout"]["standard_on"] = "opener"
    assert layout.build(book)["lessons"][0]["checks"]["standard_found"] is False


def test_analysis_pages_can_be_supplied(tmp_path):
    pages = {1: "نظرة عامة على الدرس", 2: "x", 3: "x", 4: "المعيار 10.1.1"}
    book = _analysis_book(tmp_path, pages)
    ls = layout.lessons(sq(pages), book, analysis_pages=[3])
    assert (ls[0]["opener"], ls[0]["table"], ls[0]["quiz"]) == (1, 3, 4)


def test_summarize(toy):
    s = layout.summarize(layout.build(toy))
    assert s["lessons"] == 2 and s["ok"] == 2 and s["review"] == []
    assert s["page_types"]["lesson_opener"] == 2
