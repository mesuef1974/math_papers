"""الخطة الفصلية: بنود الوزارة وأعداد حصصها أسبوعًا بأسبوع، تُحمَّل من بيانات عددية وتُحوَّل إلى بنود المحرك. حتمي، بلا Django.

الخطة في العقد القانوني (`term_plan.json` في مجلد المقرر، `apps/knowledge/domain/sources.py`) وفي الجداول (`apps.curriculum.TermPlan`)، أعداد وأرقام دروس وأنواع بنود فقط، بلا نص من وثيقة الوزارة؛ عناوين العرض من عندنا.
التحقق صارم: أسبوع يبدأ الأحد وينتهي الخميس، ومجموع حصصه خمس إلا الأيام الفاقدة فيه، ودرس مخطّط أو إثرائي غير معروف خطأ، ودرس واحد لا يكون
مخططًا وإثرائيًا معًا. الأيام الفاقدة وإغلاق الاختبارات الذي تُعقد الحصص رغمه من أقوال الخطة نفسها (حصصها في ذلك الأسبوعين أربع)، ويبقى اليوم
الفاقد المحدد افتراضًا موثّقًا في الملف.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Collection, Iterable
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from .calendar_engine import (
    ITEM_KINDS,
    WEEKDAYS,
    Item,
    Plan,
    PlanningError,
    Slot,
    Term,
)

SUNDAY, THURSDAY = 6, 3
DEFAULT_SESSIONS_PER_WEEK = 5


@dataclass(frozen=True)
class PlanEntry:
    kind: str
    periods: int
    lesson: str | None = None  # للدرس: رمزه مثل "2.6"
    unit: int | None = None  # لاختبار الوحدة
    scope: str | None = None  # "midterm" أو "final" للمراجعة والاختبار

    @property
    def key(self) -> str:
        if self.kind == "lesson":
            return f"lesson:{self.lesson}"
        if self.kind == "quiz":
            return f"quiz:u{self.unit}"
        if self.scope:
            return f"{self.kind}:{self.scope}"
        return self.kind


@dataclass(frozen=True)
class PlanWeek:
    n: int
    start: date
    end: date
    entries: tuple[PlanEntry, ...]

    @property
    def periods(self) -> int:
        return sum(e.periods for e in self.entries)


@dataclass(frozen=True)
class TermPlan:
    term_id: str
    sessions_per_week: int
    class_during_exams: tuple[date, date] | None
    lost_days: tuple[date, ...]
    enrichment_lessons: frozenset[str]
    enrichment_examples: dict[str, tuple[int, ...]]
    weeks: tuple[PlanWeek, ...]

    def lessons(self) -> list[str]:
        """الدروس المخطَّطة بترتيب ظهورها دون تكرار."""
        seen: list[str] = []
        for week in self.weeks:
            for e in week.entries:
                if e.kind == "lesson" and e.lesson not in seen:
                    seen.append(e.lesson)
        return seen

    def periods_of(self, key: str) -> int:
        return sum(e.periods for w in self.weeks for e in w.entries if e.key == key)

    @property
    def total_periods(self) -> int:
        return sum(w.periods for w in self.weeks)


def _entry(raw: dict) -> PlanEntry:
    kind = raw["kind"]
    if kind not in ITEM_KINDS:
        raise PlanningError(f"نوع بند غير معروف في الخطة: {kind}")
    entry = PlanEntry(kind, int(raw["periods"]), raw.get("lesson"), raw.get("unit"), raw.get("scope"))
    if entry.periods < 1:
        raise PlanningError(f"بند بلا حصص في الخطة: {entry.key}")
    if kind == "lesson" and not entry.lesson:
        raise PlanningError("بند درس بلا رمز")
    if kind == "quiz" and entry.unit not in (1, 2, 3):
        raise PlanningError("اختبار وحدة بلا رقم وحدة صالح")
    return entry


def term_id(semester: int) -> str:
    """معرّف الفصل في المحرك من رقمه: الفصل الأول «t1»."""
    return f"t{semester}"


def load_term_plan(path: Path) -> TermPlan:
    """خطة من ملف بصيغة العقد (`term_plan.json` في مجلد المقرر)؛ الفصل من الملف إن ذُكر وإلا الأول."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return parse_term_plan(raw, int(raw.get("semester", 1)))


def parse_term_plan(raw: dict, semester: int) -> TermPlan:
    """خطة الوزارة من بياناتها العددية (صيغة `TermPlanData` في العقد) بعد التحقق الكامل منها."""
    per_week = int(raw.get("sessions_per_week", DEFAULT_SESSIONS_PER_WEEK))
    window = raw.get("class_during_exams")
    lost = tuple(date.fromisoformat(d) for d in raw.get("lost_days", ()))
    weeks = tuple(
        PlanWeek(
            int(w["n"]),
            date.fromisoformat(w["start"]),
            date.fromisoformat(w["end"]),
            tuple(_entry(e) for e in w["items"]),
        )
        for w in raw["weeks"]
    )
    plan = TermPlan(
        term_id=term_id(semester),
        sessions_per_week=per_week,
        class_during_exams=(date.fromisoformat(window["start"]), date.fromisoformat(window["end"]))
        if window
        else None,
        lost_days=lost,
        enrichment_lessons=frozenset(raw.get("enrichment_lessons", ())),
        enrichment_examples={k: tuple(v) for k, v in raw.get("enrichment_examples", {}).items()},
        weeks=weeks,
    )
    _validate(plan)
    return plan


def _validate(plan: TermPlan) -> None:
    previous: PlanWeek | None = None
    for week in plan.weeks:
        if (
            week.start.weekday() != SUNDAY
            or week.end.weekday() != THURSDAY
            or (week.end - week.start).days != 4
        ):
            raise PlanningError(f"أسبوع {week.n} ليس من الأحد إلى الخميس")
        if previous and (week.n <= previous.n or week.start <= previous.end):
            raise PlanningError(f"أسبوع {week.n} لا يلي ما قبله")
        lost = sum(week.start <= d <= week.end for d in plan.lost_days)
        if week.periods != plan.sessions_per_week - lost:
            raise PlanningError(
                f"حصص أسبوع {week.n}: {week.periods}، والمتوقع {plan.sessions_per_week - lost}"
            )
        previous = week
    for d in plan.lost_days:
        if not any(w.start <= d <= w.end for w in plan.weeks):
            raise PlanningError(f"يوم فاقد خارج أسابيع الخطة: {d}")
    overlap = set(plan.lessons()) & plan.enrichment_lessons
    if overlap:
        raise PlanningError(f"درس مخطَّط وإثرائي معًا: {sorted(overlap)}")


def plan_items(plan: TermPlan) -> list[Item]:
    """بنود المحرك: ما امتد على أسبوعين متتاليين (مثل 2.3: حصة ثم ثلاث) بند واحد؛ وتكراره غير المتصل خطأ."""
    items: list[Item] = []
    for week in plan.weeks:
        for e in week.entries:
            if items and items[-1].id == e.key:
                items[-1] = Item(e.key, items[-1].periods + e.periods, e.kind)
            else:
                items.append(Item(e.key, e.periods, e.kind))
    repeated = sorted(k for k, n in Counter(i.id for i in items).items() if n > 1)
    if repeated:
        raise PlanningError(f"بند يتكرر منفصلًا في الخطة: {repeated}")
    return items


def term_for_plan(term: Term, plan: TermPlan) -> Term:
    """الفصل كما تُدرَّس فيه الخطة: إغلاق الاختبارات الذي تنصّ الخطة على حصص فيه لا يُعدّ إغلاقًا."""
    if plan.class_during_exams is None:
        return term
    start, end = plan.class_during_exams
    kept = tuple(c for c in term.closures if not (c.kind == "exam" and c.start >= start and c.end <= end))
    return replace(term, closures=kept)


def weekly_view(placed: Plan, plan: TermPlan) -> dict[int, dict[str, int]]:
    """حصص كل بند في كل أسبوع من الخطة كما وضعها المحرك؛ حصة خارج أسابيع الخطة تُعدّ تحت المفتاح 0."""
    out: dict[int, dict[str, int]] = {}
    for p in placed.placements:
        week = next((w.n for w in plan.weeks if w.start <= p.session.day <= w.end), 0)
        row = out.setdefault(week, {})
        row[p.item_id] = row.get(p.item_id, 0) + 1
    return out


def ministry_weekly(plan: TermPlan) -> dict[int, dict[str, int]]:
    """التوزيع الأسبوعي في بيانات الوزارة نفسها، للمقارنة بما يضعه المحرك."""
    return {w.n: dict(_sum_by_key(w)) for w in plan.weeks}


def _sum_by_key(week: PlanWeek) -> Counter:
    total: Counter = Counter()
    for e in week.entries:
        total[e.key] += e.periods
    return total


def ministry_slots(period: int = 1) -> tuple[Slot, ...]:
    """خمس حصص أسبوعيًا، واحدة كل يوم من الأحد إلى الخميس: ما تفترضه الخطة (مجموع كل أسبوع خمس)."""
    return tuple(Slot(WEEKDAYS[d], period) for d in ("sun", "mon", "tue", "wed", "thu"))


def parse_slots(rows: Iterable[tuple[str, int]]) -> tuple[Slot, ...]:
    """جدول حصص المعلم لشعبة: أزواج (اسم اليوم بالإنجليزية المختصرة، رقم الحصة)؛ المكرر والخطأ يُرفضان لا يُتجاهلان."""
    slots: list[Slot] = []
    for day, period in rows:
        if day not in WEEKDAYS:
            raise PlanningError(f"يوم غير معروف في جدول الحصص: {day}")
        slots.append(Slot(WEEKDAYS[day], int(period)))
    if len(set(slots)) != len(slots):
        raise PlanningError("حصة مكررة في جدول الحصص")
    if not slots:
        raise PlanningError("جدول حصص فارغ")
    return tuple(sorted(slots))


def check_catalog(plan: TermPlan, lessons: Collection[str], examples: dict[str, Collection[int]]) -> None:
    """الدروس والأمثلة المذكورة في الخطة موجودة في كتالوج المقرر (دروسه وأمثلتها، من فهرس مشتق أو معرفة بصياغتنا)."""
    unknown = sorted((set(plan.lessons()) | plan.enrichment_lessons) - set(lessons))
    if unknown:
        raise PlanningError(f"دروس غير موجودة في الفهرس: {unknown}")
    for lesson, numbers in plan.enrichment_examples.items():
        missing = sorted(set(numbers) - set(examples.get(lesson, ())))
        if missing:
            raise PlanningError(f"أمثلة إثرائية غير موجودة في {lesson}: {missing}")
