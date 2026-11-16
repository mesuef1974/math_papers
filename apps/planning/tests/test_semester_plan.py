"""الخطة الفصلية للعاشر: بيانات الوزارة صالحة، والمحرك يوزّعها على شعبة فيطابق الأسابيع، والتصدير يفتح."""

import json
import re
import zipfile
from datetime import date
from io import BytesIO

import pytest
from docx import Document

from apps.planning.domain.calendar_engine import DATA_DIR, PlanningError, Slot, allocate, load_terms, sessions
from apps.planning.domain.semester_plan import (
    load_term_plan,
    ministry_slots,
    ministry_weekly,
    parse_slots,
    plan_items,
    term_for_plan,
    weekly_view,
)
from apps.planning.plan_docx import plan_docx
from apps.planning.selectors import term1_schedule, term_plan

# عدد حصص كل درس في خطة الوزارة (مجموع ما يمتد على أسبوعين): مرجع مستقل عن ملف البيانات
LESSON_PERIODS = {
    "1.1": 3, "1.2": 3, "1.3": 3, "2.1": 3, "2.2": 4, "2.3": 4, "2.5": 4, "2.6": 3,
    "2.7": 3, "2.8": 3, "2.9": 3, "2.10": 3, "3.3": 3, "3.4": 3, "3.5": 3,
}  # fmt: skip
RAW_BOOK_REFS = re.compile(r"For Qatar|Savvas|ISBN", re.IGNORECASE)


@pytest.fixture(scope="module")
def plan():
    return term_plan()


def test_lesson_periods_match_the_ministry_plan(plan):
    assert {c: plan.periods_of(f"lesson:{c}") for c in plan.lessons()} == LESSON_PERIODS
    assert plan.total_periods == 63
    assert plan.periods_of("quiz:u1") == plan.periods_of("quiz:u2") == plan.periods_of("quiz:u3") == 1


def test_enrichment_lessons_are_known_and_outside_the_plan(plan):
    assert plan.enrichment_lessons == {"1.4", "2.4", "3.1", "3.2"}
    assert not set(plan.lessons()) & plan.enrichment_lessons
    assert set(plan.lessons()) | plan.enrichment_lessons == {
        f"{u}.{n}" for u, top in ((1, 4), (2, 10), (3, 5)) for n in range(1, top + 1)
    }  # الدروس الـ19 كلها: مخطَّط أو إثرائي


def test_every_week_runs_sunday_to_thursday_with_five_periods_minus_lost_days(plan):
    for w in plan.weeks:
        assert (w.start.weekday(), w.end.weekday()) == (6, 3)
        lost = sum(w.start <= d <= w.end for d in plan.lost_days)
        assert w.periods == 5 - lost
    assert [w.n for w in plan.weeks] == [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14]  # الأسبوع 9 إجازة


def test_items_merge_lessons_that_span_two_weeks(plan):
    by_id = {i.id: i.periods for i in plan_items(plan)}
    assert by_id["lesson:2.3"] == 4 and by_id["lesson:3.5"] == 3
    assert len(by_id) == 24


def test_a_section_with_five_weekly_periods_reproduces_the_ministry_weeks():
    plan, items, placed = term1_schedule()
    assert placed.unplaced == () and placed.shortfall == 0
    assert weekly_view(placed, plan) == ministry_weekly(plan)  # كل بند في أسبوعه كما في الوزارة


def test_planned_sessions_stay_inside_the_term():
    plan, _, placed = term1_schedule()
    term = load_terms()[plan.term_id]
    days = [p.session.day for p in placed.placements]
    assert term.start <= min(days) and max(days) <= term.end
    assert not any(
        date(2026, 10, 25) <= d <= date(2026, 10, 29) for d in days
    )  # إجازة منتصف الفصل تبقى مغلقة


def test_midterm_exam_window_is_taught_only_through_the_plan_rule(plan):
    term = load_terms()[plan.term_id]
    raw = sessions(term, ministry_slots())
    plain = allocate(plan_items(plan), raw)
    assert plain.shortfall > 0  # دون القاعدة يضيق الفصل عن الخطة
    taught = sessions(term_for_plan(term, plan), ministry_slots())
    assert len(taught) - len(plan.lost_days) >= plan.total_periods


def test_data_file_has_no_document_text_only_numbers_and_codes():
    raw = (DATA_DIR / "grade10_term1_plan.json").read_text(encoding="utf-8")
    assert not RAW_BOOK_REFS.search(raw)
    for w in json.loads(raw)["weeks"]:
        for e in w["items"]:
            assert set(e) <= {"kind", "periods", "lesson", "unit", "scope"}


def test_invalid_weeks_are_rejected(tmp_path):
    data = json.loads((DATA_DIR / "grade10_term1_plan.json").read_text(encoding="utf-8"))
    data["weeks"][0]["items"][1]["periods"] = 4  # أسبوع بست حصص
    bad = tmp_path / "plan.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PlanningError):
        load_term_plan(bad)


def test_enrichment_overlap_is_rejected(tmp_path):
    data = json.loads((DATA_DIR / "grade10_term1_plan.json").read_text(encoding="utf-8"))
    data["enrichment_lessons"].append("1.1")
    bad = tmp_path / "plan.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PlanningError):
        load_term_plan(bad)


def test_parse_slots_rejects_unknown_duplicate_and_empty():
    assert parse_slots([("sun", 2), ("tue", 5)]) == (Slot(1, 5), Slot(6, 2))
    for rows in ([("sunday", 1)], [("sun", 1), ("sun", 1)], []):
        with pytest.raises(PlanningError):
            parse_slots(rows)


def test_a_three_period_week_section_runs_out_of_term_and_reports_it():
    plan, _, placed = term1_schedule(parse_slots([("sun", 1), ("tue", 1), ("thu", 1)]))
    assert placed.unplaced and placed.shortfall > 0  # الفصل لا يتسع: يُبلَّغ ولا يُقصّ


def test_docx_export_is_rtl_and_lists_every_plan_entry():
    plan, _, placed = term1_schedule()
    data = plan_docx(plan, placed)
    doc = Document(BytesIO(data))
    rows = doc.tables[0].rows
    assert len(rows) == 1 + sum(len(w.entries) for w in plan.weeks)
    assert [c.text for c in rows[0].cells] == ["الأسبوع", "الزمن", "البند", "عدد الحصص", "تواريخ الحصص"]
    assert sum(int(r.cells[3].text) for r in rows[1:]) == plan.total_periods
    xml = zipfile.ZipFile(BytesIO(data)).read("word/document.xml").decode("utf-8")
    assert "<w:bidiVisual" in xml and "<w:bidi/>" in xml
    assert not RAW_BOOK_REFS.search(xml)


def test_docx_dates_of_a_split_lesson_follow_its_weeks():
    plan, _, placed = term1_schedule()
    doc = Document(BytesIO(plan_docx(plan, placed)))
    lesson_13 = [r.cells[4].text for r in doc.tables[0].rows if r.cells[2].text == "الدرس 1.3"]
    assert len(lesson_13) == 2
    assert lesson_13 == ["9/9، 10/9", "13/9"]  # حصتان في الأسبوع 2 وحصة في الأسبوع 3
