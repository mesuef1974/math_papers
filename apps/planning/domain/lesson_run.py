"""وضع الحصة: حالة حصة جارية فوق سير الحصة. حتمي، بلا ساعة ولا Django ولا توكنز.

الزمن يُمرَّر دائمًا (ثوانٍ، `now`) فلا قراءة لساعة النظام وتُختبر الحصة بمحاكاة. الحالة غير قابلة للتغيير: كل انتقال
يعيد حالة جديدة. تسجيل ما أُنجز فعلًا يكون بإغلاق الطور (`advance`) أو تخطّيه (`skip`)، و`replan` يقترح دقائق الباقي من الحصة
ضمن حدّي استراتيجية كل طور دون أن يغيّر الحالة، فإن استحال ذلك أبلغ بالعجز ولم يقصّ طورًا ولم يخمّن.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .calendar_engine import PlanningError
from .strategies import Flow, FlowStep, distribute

EPS = 1e-9


class RunError(PlanningError):
    """انتقال غير صالح في الحصة أو إعادة توزيع مستحيلة."""


@dataclass(frozen=True)
class ClosedPhase:
    phase: str
    planned: int
    actual: float  # دقائق
    skipped: bool


@dataclass(frozen=True)
class LessonRun:
    flow: Flow
    started_at: float
    phase_started_at: float
    current: int = 0
    closed: tuple[ClosedPhase, ...] = ()

    @property
    def finished(self) -> bool:
        return self.current >= len(self.flow.steps)

    @property
    def step(self) -> FlowStep:
        if self.finished:
            raise RunError("الحصة انتهت: لا طور جارٍ")
        return self.flow.steps[self.current]


@dataclass(frozen=True)
class RunReport:
    finished: bool
    planned_minutes: int
    actual_minutes: float
    phases: tuple[ClosedPhase, ...]

    @property
    def skipped(self) -> tuple[str, ...]:
        return tuple(c.phase for c in self.phases if c.skipped)


def start(flow: Flow, now: float) -> LessonRun:
    return LessonRun(flow=flow, started_at=now, phase_started_at=now)


def _since(since: float, now: float) -> float:
    if now < since:
        raise RunError("الزمن الممرَّر أسبق من بداية الطور")
    return (now - since) / 60


def phase_elapsed(run: LessonRun, now: float) -> float:
    return _since(run.phase_started_at, now)


def phase_remaining(run: LessonRun, now: float) -> float:
    """دقائق الطور الباقية؛ السالب تجاوز."""
    return run.step.minutes - phase_elapsed(run, now)


def time_left(run: LessonRun, now: float) -> float:
    """دقائق الحصة الباقية من بدايتها حتى زمنها الكامل."""
    return run.flow.period_minutes - _since(run.started_at, now)


def _close(run: LessonRun, now: float, skipped: bool) -> LessonRun:
    step = run.step
    closed = ClosedPhase(step.phase, step.minutes, phase_elapsed(run, now), skipped)
    return replace(run, current=run.current + 1, phase_started_at=now, closed=(*run.closed, closed))


def advance(run: LessonRun, now: float) -> LessonRun:
    """يغلق الطور الجاري بما استغرقه فعلًا ويبدأ التالي."""
    return _close(run, now, skipped=False)


def skip(run: LessonRun, now: float) -> LessonRun:
    """يتخطى الطور الجاري (يُسجَّل متخطًّى بما استغرقه إن بدأ) ويبدأ التالي."""
    return _close(run, now, skipped=True)


def replan(run: LessonRun, now: float) -> dict[str, int]:
    """دقائق الطور الجاري فالباقي مقيسةً من الآن، مجموعها ما بقي من زمن الحصة (مقرَّبًا إلى الأدنى)."""
    left = math.floor(time_left(run, now) + EPS)
    if left <= 0:
        raise RunError("لا زمن باقٍ في الحصة")
    elapsed = phase_elapsed(run, now)
    steps = run.flow.steps[run.current :]
    if not steps:
        raise RunError("الحصة انتهت: لا أطوار باقية")
    bounds: dict[str, tuple[int, int]] = {}
    ideal: dict[str, float] = {}
    for i, s in enumerate(steps):
        lo, hi = s.strategy.min, s.strategy.max
        planned = float(s.minutes)
        if i == 0:  # الطور الجاري: ما مضى منه لا يعود
            lo = max(0, math.ceil(lo - elapsed - EPS))
            hi = max(lo, math.floor(hi - elapsed + EPS))
            planned = max(planned - elapsed, 0.0)
        bounds[s.phase] = (lo, hi)
        ideal[s.phase] = planned
    total_ideal = sum(ideal.values())
    scale = left / total_ideal if total_ideal else 0.0
    ideal = {p: v * scale for p, v in ideal.items()}
    result = distribute(ideal, bounds, left)
    if result is None:
        need_min = sum(lo for lo, _ in bounds.values())
        need_max = sum(hi for _, hi in bounds.values())
        if left < need_min:
            raise RunError(
                f"عجز {need_min - left} دقيقة: الباقي {left} أقل من أدنى مجموع للأطوار الباقية ({need_min})"
            )
        raise RunError(
            f"فائض {left - need_max} دقيقة: الباقي {left} أكثر من أقصى مجموع للأطوار الباقية ({need_max})"
        )
    return result


def report(run: LessonRun) -> RunReport:
    return RunReport(
        finished=run.finished,
        planned_minutes=run.flow.period_minutes,
        actual_minutes=sum(c.actual for c in run.closed),
        phases=run.closed,
    )
