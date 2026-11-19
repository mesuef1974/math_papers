"""حصص الخطة الفصلية للعاشر: 48 حصة دروس و15 لغيرها، وترقيم k متصل لكل درس ولو امتد على أسبوعين، ومجموعها من جداول الخطة."""

from collections import Counter, defaultdict

import pytest
from django.db.models import Sum

from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import PlanEntry
from apps.planning.domain.plan_periods import plan_periods as derive_plan_periods
from apps.planning.domain.semester_plan import PlanEntry as Entry
from apps.planning.domain.semester_plan import PlanWeek, TermPlan
from apps.planning.selectors import plan_periods

# حصص غير الدروس في خطة الوزارة: مرجع مستقل عن ملف البيانات
OTHER_PERIODS = {"orientation": 2, "quiz": 3, "review": 4, "exam": 2, "project": 2, "support": 2}


@pytest.fixture
def periods(loaded_courses):
    return plan_periods(GRADE10_SLUG)


def test_grade10_has_48_lesson_periods_and_15_others(periods):
    kinds = Counter(p.kind for p in periods)
    assert kinds["lesson"] == 48
    assert {k: v for k, v in kinds.items() if k != "lesson"} == OTHER_PERIODS
    assert len(periods) == 63
    assert [p.number for p in periods] == list(range(1, 64))
    assert all(p.course == GRADE10_SLUG for p in periods)


def test_k_runs_contiguously_per_lesson_even_across_weeks(periods):
    by_lesson: dict[str, list] = defaultdict(list)
    for p in periods:
        if p.kind == "lesson":
            by_lesson[p.lesson].append(p)
    assert len(by_lesson) == 15
    for code, rows in by_lesson.items():
        n = len(rows)
        assert [p.k for p in rows] == list(range(1, n + 1)), code
        assert {p.n for p in rows} == {n}, code
        assert [p.number for p in rows] == list(range(rows[0].number, rows[0].number + n)), code
    spanning = {code for code, rows in by_lesson.items() if len({p.week for p in rows}) > 1}
    assert {"1.3", "2.3", "2.5", "2.8", "2.10", "3.3", "3.5"} <= spanning
    weeks_13 = [(p.week, p.k) for p in by_lesson["1.3"]]
    assert weeks_13 == [(2, 1), (2, 2), (3, 3)]


def test_periods_per_lesson_equal_plan_entry_periods_in_the_tables(periods):
    rows = (
        PlanEntry.objects.filter(week__plan__course__slug=GRADE10_SLUG, kind="lesson")
        .values("lesson__code")
        .annotate(total=Sum("periods"))
    )
    expected = {r["lesson__code"]: r["total"] for r in rows}
    derived = Counter(p.lesson for p in periods if p.kind == "lesson")
    assert derived == expected
    assert sum(expected.values()) == 48


def test_every_period_points_to_its_week_entry(periods):
    per_entry = Counter((p.week, p.entry) for p in periods)
    for (week, entry), count in per_entry.items():
        assert count == entry.periods, (week, entry)


def test_derivation_is_pure_and_numbers_each_entry_key():
    from datetime import date

    weeks = (
        PlanWeek(1, date(2026, 8, 30), date(2026, 9, 3), (Entry("review", 1, scope="midterm"), Entry("lesson", 2, "1.1"))),
        PlanWeek(2, date(2026, 9, 6), date(2026, 9, 10), (Entry("lesson", 1, "1.1"), Entry("review", 1, scope="final"))),
    )
    plan = TermPlan("t1", 5, None, (), frozenset(), {}, weeks)
    got = [(p.key, p.k, p.n, p.week, p.number) for p in derive_plan_periods("c", plan)]
    assert got == [
        ("review:midterm", 1, 1, 1, 1),
        ("lesson:1.1", 1, 3, 1, 2),
        ("lesson:1.1", 2, 3, 1, 3),
        ("lesson:1.1", 3, 3, 2, 4),
        ("review:final", 1, 1, 2, 5),
    ]
