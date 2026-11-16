"""وضع الحصة بمحاكاة بزمن مُمرَّر: التسجيل والتخطي وإعادة التوزيع ضمن الحدود أو الإبلاغ بالعجز."""

import pytest

from apps.planning.domain.lesson_run import (
    RunError,
    advance,
    phase_remaining,
    replan,
    report,
    skip,
    start,
    time_left,
)
from apps.planning.domain.strategies import PHASES, build_flow

T0 = 10_000.0


def _at(minutes: float) -> float:
    return T0 + minutes * 60


def test_on_time_run_records_exactly_the_plan():
    flow = build_flow(45)
    run = start(flow, T0)
    clock = 0
    for step in flow.steps:
        assert run.step.phase == step.phase
        clock += step.minutes
        run = advance(run, _at(clock))
    rep = report(run)
    assert rep.finished and rep.actual_minutes == pytest.approx(45) and rep.planned_minutes == 45
    assert [c.actual for c in rep.phases] == [s.minutes for s in flow.steps]
    assert not rep.skipped


@pytest.mark.parametrize("period", range(35, 76))
def test_replan_on_schedule_returns_the_plan_unchanged(period):
    flow = build_flow(period)
    run, clock = start(flow, T0), 0
    for i, step in enumerate(flow.steps):
        assert replan(run, _at(clock)) == {s.phase: s.minutes for s in flow.steps[i:]}
        clock += step.minutes
        run = advance(run, _at(clock))


def test_overrun_shrinks_the_remaining_phases_within_their_bounds():
    flow = build_flow(60)
    run, clock = start(flow, T0), 0
    for step in flow.steps[:3]:  # الأطوار الثلاثة الأولى في وقتها
        clock += step.minutes
        run = advance(run, _at(clock))
    clock += flow.steps[3].minutes + 3  # طور التدريب تجاوز ثلاث دقائق
    run = advance(run, _at(clock))
    planned = {s.phase: s.minutes for s in flow.steps[4:]}
    plan = replan(run, _at(clock))
    assert sum(plan.values()) == 60 - clock and sum(plan.values()) == sum(planned.values()) - 3
    assert all(plan[s.phase] <= planned[s.phase] for s in flow.steps[4:])
    for step in flow.steps[4:]:
        assert step.strategy.min <= plan[step.phase] <= step.strategy.max


def test_hopeless_overrun_reports_the_shortfall_instead_of_trimming():
    flow = build_flow(45)
    run = advance(start(flow, T0), _at(40))  # الافتتاح استغرق 40 دقيقة
    with pytest.raises(RunError, match="عجز"):
        replan(run, _at(40))


def test_time_left_after_the_period_has_no_plan():
    run = start(build_flow(45), T0)
    with pytest.raises(RunError):
        replan(run, _at(45))


def test_current_phase_that_hit_its_maximum_gets_zero_minutes():
    flow = build_flow(45)
    run = start(flow, T0)
    plan = replan(run, _at(flow.steps[0].strategy.max))
    assert plan[PHASES[0]] == 0


def test_skip_marks_the_phase_and_keeps_the_time_it_took():
    flow = build_flow(45)
    run = skip(start(flow, T0), _at(1))
    assert report(run).skipped == (PHASES[0],)
    assert report(run).phases[0].actual == pytest.approx(1)
    assert run.step.phase == PHASES[1]
    # الدقائق المتروكة تزيد على الباقي: الأطوار الخمسة الباقية تتسع لـ44 دقيقة
    assert sum(replan(run, _at(1)).values()) == 44


def test_phase_remaining_goes_negative_on_overrun_and_state_is_immutable():
    flow = build_flow(45)
    run = start(flow, T0)
    first = flow.steps[0].minutes
    assert phase_remaining(run, _at(first - 1)) == pytest.approx(1)
    assert phase_remaining(run, _at(first + 2)) == pytest.approx(-2)
    assert time_left(run, _at(10)) == pytest.approx(35)
    advance(run, _at(first))
    assert run.current == 0 and run.closed == ()  # الحالة الأصلية لم تتغير


def test_invalid_transitions_raise():
    flow = build_flow(45)
    run = start(flow, T0)
    with pytest.raises(RunError):
        advance(run, T0 - 1)  # زمن أسبق من بداية الطور
    for i in range(len(PHASES)):
        run = advance(run, _at(i + 1))
    with pytest.raises(RunError):
        advance(run, _at(10))
    with pytest.raises(RunError):
        run.step


def test_replan_floors_the_fractional_time_left():
    run = start(build_flow(45), T0)
    assert sum(replan(run, _at(0.5)).values()) == 44  # 44.5 دقيقة باقية: لا نعد دقيقة لم تكتمل


def test_replan_mid_phase_counts_what_already_elapsed_against_the_maximum():
    flow = build_flow(45)
    first = flow.steps[0]
    elapsed = first.strategy.max - 1
    plan = replan(start(flow, T0), _at(elapsed))
    assert plan[first.phase] <= 1  # لم يبقَ للطور الجاري إلا دقيقة قبل حدّه الأقصى


def test_replan_reports_surplus_when_the_phases_cannot_absorb_the_time_left():
    # حصة بأقصى مجموع (75): الافتتاح انتهى بعد دقيقة، ثم مضى على الاستكشاف ما يساوي أقصى الافتتاح؛
    # الباقي أكبر من أقصى ما تتسع له الأطوار الباقية بعد خصم ما مضى من الطور الجاري، فيُبلَّغ الفائض لا يُجبَر.
    flow = build_flow(75)
    run = advance(start(flow, T0), _at(1))
    with pytest.raises(RunError, match="فائض"):
        replan(run, _at(1 + flow.steps[0].strategy.max))
