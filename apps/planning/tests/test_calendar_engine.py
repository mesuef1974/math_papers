"""محرك التقويم: أيام الدوام تستثني المغلقات، والتوزيع يحفظ الترتيب ويستوفي الحصص، وإعادة التوزيع تُبقي الماضي."""

from datetime import date

import pytest

from apps.planning.domain.calendar_engine import (
    Closure,
    Item,
    PlanningError,
    Session,
    Slot,
    Term,
    allocate,
    load_terms,
    moves,
    reflow,
    sessions,
    teaching_days,
)

SUN, MON, TUE, WED, THU, FRI, SAT = 6, 0, 1, 2, 3, 4, 5
THREE_A_WEEK = [Slot(SUN, 2), Slot(TUE, 3), Slot(WED, 1)]


@pytest.fixture(scope="module")
def terms():
    return load_terms()


def small_term(**over):
    base = {"id": "x", "name": "تجريبي", "start": date(2026, 9, 6), "end": date(2026, 9, 24)}
    return Term(**{**base, **over})


def test_calendar_dates_fall_on_the_expected_weekdays(terms):
    assert terms["t1"].start.weekday() == SUN  # بدء الطلبة الأحد 30/8/2026
    assert terms["t1"].closures[1].start.weekday() == SUN  # إجازة منتصف الفصل تبدأ الأحد 25/10
    assert terms["t2"].start == date(2027, 1, 4)


def test_first_term_teaching_days_match_hand_count(terms):
    """14 أسبوعًا كاملًا من 30/8 إلى 3/12 بخمسة أيام = 70، تُطرح منها 8 أيام اختبارات منتصف الفصل و5 إجازة = 57."""
    days = teaching_days(terms["t1"])
    assert len(days) == 57
    assert days[0] == date(2026, 8, 30) and days[-1] == date(2026, 12, 3)


@pytest.mark.parametrize("term_id", ["t1", "t2"])
def test_teaching_days_are_sorted_weekdays_outside_every_closure(terms, term_id):
    term = terms[term_id]
    days = teaching_days(term)
    assert days == sorted(set(days))
    assert all(d.weekday() not in (FRI, SAT) for d in days)
    assert all(term.start <= d <= term.end for d in days)
    assert not [d for d in days if any(c.covers(d) for c in term.closures)]


def test_extra_closure_removes_that_day_only(terms):
    base = teaching_days(terms["t1"])
    lost = date(2026, 9, 15)
    after = teaching_days(terms["t1"], [Closure(lost, lost)])
    assert set(base) - set(after) == {lost}


def test_sessions_follow_the_weekly_slots_in_order():
    term = small_term()
    got = sessions(term, THREE_A_WEEK)
    assert got == sorted(got)
    assert {(s.day.weekday(), s.period) for s in got} == {(SUN, 2), (TUE, 3), (WED, 1)}
    assert len(got) == 9  # ثلاثة أسابيع (6 إلى 24 أيلول) × 3 حصص
    assert sessions(term, [Slot(SUN, 2), Slot(SUN, 2)]) == sessions(
        term, [Slot(SUN, 2)]
    )  # تكرار الخانة لا يضاعفها


def test_allocate_keeps_order_and_fills_each_items_periods():
    free = sessions(small_term(), THREE_A_WEEK)
    items = [Item("1.1", 3), Item("1.2", 2), Item("quiz", 1, "quiz")]
    plan = allocate(items, free)
    assert plan.unplaced == () and plan.shortfall == 0
    assert [p.item_id for p in plan.placements] == ["1.1"] * 3 + ["1.2"] * 2 + ["quiz"]
    assert [p.session for p in plan.placements] == free[:6]
    assert [(p.part, p.parts) for p in plan.of("1.1")] == [(1, 3), (2, 3), (3, 3)]


def test_item_that_does_not_fit_is_reported_not_cut_and_blocks_those_after():
    free = sessions(small_term(), THREE_A_WEEK)  # 9 حصص
    plan = allocate([Item("a", 5), Item("b", 5), Item("c", 1)], free)
    assert [p.item_id for p in plan.placements] == ["a"] * 5
    assert plan.unplaced == ("b", "c")  # التسلسل لا يقفز: «c» لا يتقدم على «b»
    assert plan.shortfall == 6


def test_reflow_keeps_the_past_and_shifts_the_rest_after_a_lost_day():
    term = small_term()
    items = [Item("a", 3), Item("b", 3), Item("c", 2)]
    before = allocate(items, sessions(term, THREE_A_WEEK))
    today = before.placements[3].session.day  # أول حصة من «b»
    lost = before.placements[4].session.day  # حصة «b» الثانية تضيع
    after = reflow(items, term, THREE_A_WEEK, before, today, lost=[lost])
    assert after.placements[:3] == before.placements[:3]
    assert all(p.session.day != lost for p in after.placements)
    assert [p.item_id for p in after.placements] == ["a"] * 3 + ["b"] * 3 + ["c"] * 2
    assert after.placements[-1].session > before.placements[-1].session
    assert [m.item_id for m in moves(before, after, items)] == ["b", "c"]


def test_reflow_continues_an_item_started_before_today():
    term = small_term()
    items = [Item("a", 4), Item("b", 1)]
    before = allocate(items, sessions(term, THREE_A_WEEK))
    today = before.placements[2].session.day  # «a» أُنجزت حصتان قبل هذا اليوم أو معه
    done = [p for p in before.placements if p.session.day < today]
    after = reflow(items, term, THREE_A_WEEK, before, today)
    assert after.placements == before.placements  # بلا ضياع لا يتغير شيء
    redo = reflow(items, term, THREE_A_WEEK, before, today, lost=[today])
    parts = [p.part for p in redo.of("a")]
    assert parts == [1, 2, 3, 4][: len(parts)] and parts == sorted(parts)
    assert len(redo.of("a")) == 4 and redo.of("a")[: len(done)] == tuple(p for p in done if p.item_id == "a")


def test_reflow_reports_overflow_when_lost_days_leave_no_room():
    term = small_term()
    free = sessions(term, THREE_A_WEEK)
    items = [Item("a", 4), Item("b", 5)]  # 9 حصص تملأ الفصل كله
    before = allocate(items, free)
    assert before.unplaced == ()
    after = reflow(items, term, THREE_A_WEEK, before, free[4].day, lost=[free[6].day])
    assert after.unplaced == ("b",) and after.shortfall > 0
    assert [p.item_id for p in after.placements] == ["a"] * 4  # الماضي كما أُنجز


def test_closures_inside_the_term_are_skipped_by_sessions():
    holiday = Closure(date(2026, 9, 8), date(2026, 9, 10), "holiday", "عطلة")
    term = small_term(closures=(holiday,))
    days = {s.day for s in sessions(term, THREE_A_WEEK)}
    assert not days & {date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 10)}


def test_invalid_inputs_are_rejected():
    with pytest.raises(PlanningError):
        Closure(date(2026, 9, 2), date(2026, 9, 1))
    with pytest.raises(PlanningError):
        Closure(date(2026, 9, 1), date(2026, 9, 2), "unknown")
    with pytest.raises(PlanningError):
        Slot(7, 1)
    with pytest.raises(PlanningError):
        Slot(SUN, 0)
    with pytest.raises(PlanningError):
        Item("x", 0)
    with pytest.raises(PlanningError):
        Item("x", 1, "exam")
    with pytest.raises(PlanningError):
        small_term(end=date(2026, 9, 1))
    with pytest.raises(PlanningError):
        allocate([Item("x", 1), Item("x", 2)], [Session(date(2026, 9, 6), 1)])
