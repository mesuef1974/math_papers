"""حلقة ما بعد الحصة: مستويات الإتقان وقرار إعادة التدريس وأثره على الخطة عبر reflow."""

from datetime import date

import pytest

from apps.planning.domain.calendar_engine import Item, PlanningError, Slot, Term, allocate, reflow, sessions
from apps.planning.domain.feedback import (
    ClassOutcome,
    apply_decision,
    decide,
    mastery_level,
)

SUN, TUE = 6, 1


@pytest.mark.parametrize(
    ("rate", "level"),
    [
        (1.0, "mastered"),
        (0.8, "mastered"),
        (0.79, "developing"),
        (0.5, "developing"),
        (0.49, "not_yet"),
        (0.0, "not_yet"),
    ],
)
def test_mastery_level_boundaries(rate, level):
    assert mastery_level(rate) == level


def test_outcome_validation():
    for bad in (
        {"attempted": 0, "correct": 0},
        {"attempted": 5, "correct": 6},
        {"attempted": 5, "correct": -1},
        {"attempted": 5, "correct": 3, "pace": "fastest"},
        {"attempted": 5, "correct": 3, "obstacles": frozenset({"mood"})},
    ):
        with pytest.raises(PlanningError):
            ClassOutcome("1.1", **bad)


def test_decision_table():
    def d(correct, attempted=30, **kw):
        return decide(ClassOutcome("1.1", attempted, correct, **kw))

    assert (d(27).action, d(27).extra_periods) == ("advance", 0)
    assert (d(18).action, d(18).extra_periods) == ("quick_review", 0)  # 0.6
    assert (d(12).action, d(12).extra_periods) == ("reteach", 1)  # 0.4
    assert (d(8).action, d(8).extra_periods) == ("reteach", 2)  # 0.27: تعثر شديد
    assert (d(9).action, d(9).extra_periods) == ("reteach", 1)  # 0.30 بالضبط ليس شديدًا


def test_notes_carry_pace_and_obstacles_in_a_stable_order():
    out = ClassOutcome("1.1", 10, 9, pace="slow", obstacles=frozenset({"time", "concept"}))
    assert decide(out).notes == ("pace_slow", "obstacle_concept", "obstacle_time")


ITEMS = [Item("1.1", 2), Item("1.2", 2), Item("1.3", 2)]


def test_apply_decision_inserts_a_review_right_after_the_lesson():
    decision = decide(ClassOutcome("1.1", 30, 12))
    out = apply_decision(ITEMS, decision)
    assert [(i.id, i.periods, i.kind) for i in out] == [
        ("1.1", 2, "lesson"),
        ("1.1-reteach", 1, "review"),
        ("1.2", 2, "lesson"),
        ("1.3", 2, "lesson"),
    ]


def test_apply_decision_is_idempotent_and_replaces_the_previous_review():
    once = apply_decision(ITEMS, decide(ClassOutcome("1.1", 30, 12)))
    assert apply_decision(once, decide(ClassOutcome("1.1", 30, 12))) == once
    worse = apply_decision(once, decide(ClassOutcome("1.1", 30, 3)))
    assert [i.periods for i in worse if i.id == "1.1-reteach"] == [2]
    healed = apply_decision(worse, decide(ClassOutcome("1.1", 30, 29)))
    assert healed == ITEMS  # بعد الإتقان يزول بند المراجعة


def test_apply_decision_rejects_an_unknown_lesson():
    with pytest.raises(PlanningError):
        apply_decision(ITEMS, decide(ClassOutcome("9.9", 30, 12)))


def test_reteach_pushes_the_following_lessons_by_one_session_through_reflow():
    term = Term(id="x", name="تجريبي", start=date(2026, 9, 6), end=date(2026, 10, 31))
    slots = [Slot(SUN, 1), Slot(TUE, 1)]
    before = allocate(ITEMS, sessions(term, slots))
    first_two = [p for p in before.placements if p.item_id == "1.1"]
    today = max(p.session.day for p in first_two).replace(day=max(p.session.day for p in first_two).day + 1)

    items = apply_decision(ITEMS, decide(ClassOutcome("1.1", 30, 12)))
    after = reflow(items, term, slots, before, today)

    day = lambda plan, item: [p.session.day for p in plan.placements if p.item_id == item]  # noqa: E731
    assert day(after, "1.1") == day(before, "1.1")  # الماضي لم يتغير
    review = day(after, "1.1-reteach")
    assert len(review) == 1 and review[0] >= today
    assert day(after, "1.2")[0] > day(before, "1.2")[0]  # أُزيح بحصة
    assert not after.unplaced
