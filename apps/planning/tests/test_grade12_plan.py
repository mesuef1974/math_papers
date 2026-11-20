"""خطة الثاني عشر الفصلية: تُحمَّل بالمحمِّل الواحد وتُقرأ من الجداول، وفهرسه من دروسه بصياغتنا."""

import pytest

from apps.curriculum.courses import GRADE10_SLUG, GRADE12_SLUG
from apps.curriculum.models import Lesson, PlanEnrichment, PlanEntry, PlanWeek, TermPlan
from apps.knowledge.domain.contract import read_source, source_index
from apps.knowledge.selectors import course_index, example_numbers
from apps.knowledge.services import load_course
from apps.planning.domain.calendar_engine import PlanningError
from apps.planning.domain.prep_checks import PASS
from apps.planning.domain.semester_plan import parse_slots
from apps.planning.selectors import lesson_preps, term1_schedule, term_plan

pytestmark = pytest.mark.usefixtures("loaded_courses")

ENRICHMENT_EXAMPLES = {"2.2": (6,), "2.6": (5,), "2.8": (4, 5), "2.9": (6,), "3.5": (4,)}
MIDTERM_WEEKS = {7, 8}  # أسبوعا اختبارات منتصف الفصل: أربع حصص من ست


def test_loader_writes_the_grade12_plan_and_reloading_changes_nothing():
    plan = TermPlan.objects.get(course__slug=GRADE12_SLUG)
    assert (plan.source.slug, plan.sessions_per_week) == ("g12-sci-s1-term-plan", 6)
    assert list(plan.lost_days) == ["2026-10-14", "2026-10-15", "2026-10-21", "2026-10-22"]
    assert (plan.class_during_exams_start.isoformat(), plan.class_during_exams_end.isoformat()) == (
        "2026-10-13",
        "2026-10-22",
    )
    numbers = list(PlanWeek.objects.filter(plan=plan).order_by("number").values_list("number", flat=True))
    assert len(numbers) == 13 and 9 not in numbers  # الأسبوع 9 إجازة منتصف الفصل
    assert not PlanEntry.objects.filter(week__plan=plan, lesson__code="3.6").exists()
    whole = PlanEnrichment.objects.filter(plan=plan, example__isnull=True)
    assert list(whole.values_list("lesson__code", flat=True)) == ["3.6"]
    assert load_course(GRADE12_SLUG).total == 0


def test_term_plan_reads_grade12_from_our_lessons():
    assert len(course_index(GRADE12_SLUG).lessons) == 19  # فهرسه من دروسه بصياغتنا لا من فهرس مشتق
    plan = term_plan(GRADE12_SLUG)
    assert plan == read_source(GRADE12_SLUG).term_plan.to_domain(1)
    assert plan.sessions_per_week == 6
    assert [w.n for w in plan.weeks] == [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14]
    assert plan.enrichment_lessons == {"3.6"} and "3.6" not in plan.lessons()
    assert dict(plan.enrichment_examples) == ENRICHMENT_EXAMPLES
    for week in plan.weeks:
        assert week.periods == (4 if week.n in MIDTERM_WEEKS else 6), week.n


def test_grade12_examples_come_from_our_lesson_files():
    numbers = example_numbers(GRADE12_SLUG)
    assert numbers["2.8"] == [1, 2, 3, 4, 5]
    for lesson, enrichment in ENRICHMENT_EXAMPLES.items():
        assert set(enrichment) <= set(numbers[lesson]), lesson


def test_grade10_catalog_is_still_its_derived_index():
    index = source_index(GRADE10_SLUG)
    assert example_numbers(GRADE10_SLUG) == {
        lesson.lesson: [e.n for e in lesson.examples] for lesson in index.lessons if lesson.examples
    }
    assert term_plan(GRADE10_SLUG) == read_source(GRADE10_SLUG).term_plan.to_domain(1)


def test_missing_enrichment_example_in_grade12_is_rejected():
    plan = TermPlan.objects.get(course__slug=GRADE12_SLUG)
    lesson = Lesson.objects.get(course__slug=GRADE12_SLUG, code="2.8")
    PlanEnrichment.objects.create(plan=plan, lesson=lesson, example=9)
    with pytest.raises(PlanningError, match=r"أمثلة إثرائية غير موجودة في 2\.8: \[9\]"):
        term_plan(GRADE12_SLUG)


def test_grade12_schedule_places_every_planned_period():
    """ست حصص أسبوعيًا (حصتان يوم الأحد): الأربعاء والخميس الفاقدان يتركان أربعًا في أسبوعي المنتصف."""
    six = parse_slots([("sun", 1), ("sun", 2), ("mon", 1), ("tue", 1), ("wed", 1), ("thu", 1)])
    plan, items, placed = term1_schedule(six, course=GRADE12_SLUG)
    assert sum(item.periods for item in items) == plan.total_periods == 74
    assert not placed.unplaced


APPROVED_UNITS_G12 = {1}  # وحدات الثاني عشر التي اعتمد المالك نصوصها (prep/unit-<n>.json)


def test_grade12_approved_units_pass_objectives_and_approval():
    """حصص الوحدة المعتمدة تجتاز T2 وT2c، وكل مثال أساسي في حصة واحدة؛ ما سواها معلَّق لا فاشل."""
    preps = [row for row in lesson_preps(GRADE12_SLUG) if row.prep.unit in APPROVED_UNITS_G12]
    assert [row.prep.lesson for row in preps].count("1.3") == 3 and len(preps) == 15
    for row in preps:
        by = {r.code: r for r in row.checks}
        assert by["T2"].status == PASS, (row.prep.lesson, row.prep.k, by["T2"])
        assert by["T2c"].status == PASS, (row.prep.lesson, row.prep.k, by["T2c"])
    placed: dict[str, list[int]] = {}
    for row in preps:
        placed.setdefault(row.prep.lesson, []).extend(e.n for e in row.prep.examples)
    assert placed == {
        "1.1": [1, 2, 3, 4, 5, 6],
        "1.2": [1, 2, 3, 4, 5, 6],
        "1.3": [1, 2, 3, 4],
        "1.4": [1, 2, 3, 4, 5],
    }
