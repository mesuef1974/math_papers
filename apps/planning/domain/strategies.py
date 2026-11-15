"""مكتبة الاستراتيجيات ومنتقٍ ومولّد سير الحصة بالزمن: حتمي، بلا Django ولا توكنز.

المكتبة (`data/strategies.json`) بصياغتنا لا من كتاب ولا دليل: لكل استراتيجية طور من أطوار الحصة، ومستويات بلوم وDOK التي
تخدمها، وطريقة التجميع، والموارد اللازمة، وحدّا دقائقها. المنتقي يرتّب بالدرجات (تطابق بلوم وDOK وتمام الزمن المثالي) ويحترم
الموارد المتاحة. المولّد يقسم زمن الحصة على الأطوار بأوزان ثابتة، ويختار لكل طور استراتيجية، ثم يضبط الدقائق ضمن حدّي كل
استراتيجية ليساوي المجموع زمن الحصة تمامًا؛ فإن استحال ذلك رفع `FlowError` ولم يقصّ ولم يخمّن.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from pathlib import Path

from .calendar_engine import DATA_DIR, PlanningError

PHASES = ("opening", "explore", "explain", "practice", "check", "close")
PHASE_WEIGHTS = {
    "opening": 0.10,
    "explore": 0.20,
    "explain": 0.25,
    "practice": 0.25,
    "check": 0.12,
    "close": 0.08,
}
BLOOMS = ("تذكر", "فهم", "تطبيق", "تحليل", "تقويم", "إبداع")
GROUPINGS = ("individual", "pairs", "group", "whole")
RESOURCES = ("devices", "graph_paper", "calculators", "whiteboards", "printed_sheets")
DEFAULT_PERIOD_MINUTES = 45  # افتراض غير مؤكد من الوزارة؛ يُمرَّر الزمن الحقيقي دائمًا من جدول المعلم


class FlowError(PlanningError):
    """لا سير ممكن لهذا الزمن بهذه القيود."""


@dataclass(frozen=True)
class Strategy:
    slug: str
    title: str
    phase: str
    min: int
    max: int
    bloom: tuple[str, ...]
    dok: tuple[int, ...]
    grouping: str
    needs: tuple[str, ...]
    steps: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.phase not in PHASES:
            raise PlanningError(f"طور غير معروف في {self.slug}: {self.phase}")
        if not 1 <= self.min <= self.max:
            raise PlanningError(f"حدّا الدقائق غير صالحين في {self.slug}")
        if not set(self.bloom) <= set(BLOOMS) or not self.bloom:
            raise PlanningError(f"مستويات بلوم غير صالحة في {self.slug}")
        if not set(self.dok) <= {1, 2, 3, 4} or not self.dok:
            raise PlanningError(f"مستويات DOK غير صالحة في {self.slug}")
        if self.grouping not in GROUPINGS:
            raise PlanningError(f"تجميع غير معروف في {self.slug}: {self.grouping}")
        if not set(self.needs) <= set(RESOURCES):
            raise PlanningError(f"مورد غير معروف في {self.slug}")
        if not self.steps:
            raise PlanningError(f"استراتيجية بلا خطوات: {self.slug}")


@dataclass(frozen=True)
class LessonProfile:
    """ما يطلبه الدرس: مستويات بلوم لأهدافه وأعماق DOK لتمارينه (من الفهرس المشتق)."""

    bloom: frozenset[str] = frozenset()
    dok: frozenset[int] = frozenset()


NO_PROFILE = LessonProfile()


@dataclass(frozen=True)
class FlowStep:
    phase: str
    strategy: Strategy
    minutes: int
    start: int  # الدقيقة التي يبدأ عندها الطور من بداية الحصة


@dataclass(frozen=True)
class Flow:
    period_minutes: int
    steps: tuple[FlowStep, ...]

    @property
    def total(self) -> int:
        return sum(s.minutes for s in self.steps)


def load_library(path: Path | None = None) -> tuple[Strategy, ...]:
    raw = json.loads((path or DATA_DIR / "strategies.json").read_text(encoding="utf-8"))
    library = tuple(
        Strategy(
            slug=r["slug"],
            title=r["title"],
            phase=r["phase"],
            min=r["min"],
            max=r["max"],
            bloom=tuple(r["bloom"]),
            dok=tuple(r["dok"]),
            grouping=r["grouping"],
            needs=tuple(r.get("needs", ())),
            steps=tuple(r["steps"]),
        )
        for r in raw
    )
    slugs = [s.slug for s in library]
    if len(set(slugs)) != len(slugs):
        raise PlanningError("معرّفات استراتيجيات مكررة")
    for phase in PHASES:
        if not any(s.phase == phase and not s.needs for s in library):
            raise PlanningError(f"الطور {phase} بلا استراتيجية تعمل بلا موارد")
    return library


def _score(strategy: Strategy, profile: LessonProfile, ideal: float) -> int:
    score = 2 * len(profile.bloom & set(strategy.bloom)) + 2 * len(profile.dok & set(strategy.dok))
    return score + (1 if strategy.min <= ideal <= strategy.max else 0)


def select(
    library: Iterable[Strategy],
    phase: str,
    profile: LessonProfile = NO_PROFILE,
    resources: Collection[str] = (),
    ideal_minutes: float = 0,
    exclude: Collection[str] = (),
) -> list[Strategy]:
    """استراتيجيات الطور المتاحة بمواردها، مرتبة من الأنسب؛ التعادل بالمعرّف فالنتيجة حتمية."""
    available = set(resources)
    candidates = [
        s for s in library if s.phase == phase and set(s.needs) <= available and s.slug not in exclude
    ]
    return sorted(candidates, key=lambda s: (-_score(s, profile, ideal_minutes), s.slug))


def _split(chosen: dict[str, Strategy], period: int) -> dict[str, int]:
    """دقائق كل طور: المثالي مقرَّبًا ومحصورًا في حدّي استراتيجيته، ثم يُوزَّع الفرق بالأقرب إلى مثاليه."""
    ideal = {p: period * PHASE_WEIGHTS[p] for p in PHASES}
    minutes = {p: min(max(round(ideal[p]), chosen[p].min), chosen[p].max) for p in PHASES}
    diff = period - sum(minutes.values())
    while diff != 0:
        step = 1 if diff > 0 else -1
        room = [p for p in PHASES if (minutes[p] < chosen[p].max if step > 0 else minutes[p] > chosen[p].min)]
        if not room:
            raise FlowError(f"لا توزيع للدقائق يساوي {period} ضمن حدود الاستراتيجيات المختارة")
        pick = max(room, key=lambda p: (ideal[p] - minutes[p]) * step)
        minutes[pick] += step
        diff -= step
    return minutes


def build_flow(
    period_minutes: int = DEFAULT_PERIOD_MINUTES,
    profile: LessonProfile = NO_PROFILE,
    library: Iterable[Strategy] | None = None,
    resources: Collection[str] = (),
) -> Flow:
    """سير حصة بستة أطوار مجموع دقائقها زمن الحصة تمامًا."""
    library = tuple(library) if library is not None else load_library()
    ranked = {p: select(library, p, profile, resources, period_minutes * PHASE_WEIGHTS[p]) for p in PHASES}
    empty = [p for p, r in ranked.items() if not r]
    if empty:
        raise FlowError(f"لا استراتيجية متاحة للطور: {empty[0]}")
    chosen = {p: ranked[p][0] for p in PHASES}

    def total(attr: str) -> int:
        return sum(getattr(chosen[p], attr) for p in PHASES)

    # زمن قصير: نبدّل بأرخص بديل يوفّر أكثر؛ زمن طويل: بأوسع بديل يزيد أكثر. كل تبديل يقلّص الفجوة وإلا تُبلَّغ الاستحالة.
    while total("min") > period_minutes:
        gains = [
            (chosen[p].min - alt.min, p, alt)
            for p in PHASES
            for alt in [min(ranked[p], key=lambda s: (s.min, s.slug))]
            if alt.min < chosen[p].min
        ]
        if not gains:
            raise FlowError(f"الزمن {period_minutes} دقيقة أقل من أدنى مجموع ممكن ({total('min')})")
        _, p, alt = max(gains, key=lambda g: (g[0], -PHASES.index(g[1])))
        chosen[p] = alt
    while total("max") < period_minutes:
        gains = [
            (alt.max - chosen[p].max, p, alt)
            for p in PHASES
            for alt in [max(ranked[p], key=lambda s: (s.max, s.slug))]
            if alt.max > chosen[p].max
        ]
        if not gains:
            raise FlowError(f"الزمن {period_minutes} دقيقة أكثر من أقصى مجموع ممكن ({total('max')})")
        _, p, alt = max(gains, key=lambda g: (g[0], -PHASES.index(g[1])))
        chosen[p] = alt

    minutes = _split(chosen, period_minutes)
    steps: list[FlowStep] = []
    cursor = 0
    for phase in PHASES:
        steps.append(FlowStep(phase, chosen[phase], minutes[phase], cursor))
        cursor += minutes[phase]
    return Flow(period_minutes, tuple(steps))
