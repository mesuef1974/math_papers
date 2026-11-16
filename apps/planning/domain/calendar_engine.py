"""محرك التقويم والخطة الفصلية: حتمي، بلا Django ولا قاعدة بيانات ولا توكنز.

المدخلات: فصل بحدّه ومغلقاته (اختبارات وإجازات وعطل)، وحصص الشعبة الأسبوعية، وتسلسل بنود (دروس ومراجعات واختبارات
قصيرة) لكل منها عدد حصص. المخرج: خطة توزّع البنود بترتيبها على الحصص الفعلية، وبند لا يتسع له الفصل يُبلَّغ به ولا يُقصّ.
عند ضياع يوم تُعاد الخطة من اليوم الجاري: ما مضى يبقى كما أُنجز، وما بعده يُعاد توزيعه على الحصص المتبقية.
أيام الأسبوع بترقيم بايثون (الاثنين 0 … الأحد 6).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

CLOSURE_KINDS = ("exam", "break", "holiday", "other")
ITEM_KINDS = ("lesson", "review", "quiz", "orientation", "exam", "project", "support")
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
DEFAULT_WEEKDAYS = (6, 0, 1, 2, 3)  # الأحد إلى الخميس
MAX_PERIOD = 9
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class PlanningError(ValueError):
    """مدخل تخطيط غير صالح (حد مقلوب، حصة خارج المدى، بند بلا حصص)."""


@dataclass(frozen=True)
class Closure:
    start: date
    end: date
    kind: str = "other"
    label: str = ""

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise PlanningError(f"إغلاق ينتهي قبل أن يبدأ: {self.start} إلى {self.end}")
        if self.kind not in CLOSURE_KINDS:
            raise PlanningError(f"نوع إغلاق غير معروف: {self.kind}")

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.end


@dataclass(frozen=True)
class Term:
    id: str
    name: str
    start: date
    end: date  # آخر يوم يصلح للتدريس (شامل)
    closures: tuple[Closure, ...] = ()
    weekdays: tuple[int, ...] = DEFAULT_WEEKDAYS

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise PlanningError(f"فصل ينتهي قبل أن يبدأ: {self.id}")
        if not self.weekdays or any(d not in range(7) for d in self.weekdays):
            raise PlanningError("أيام الدوام يجب أن تكون من 0 إلى 6")


@dataclass(frozen=True, order=True)
class Slot:
    weekday: int
    period: int

    def __post_init__(self) -> None:
        if self.weekday not in range(7):
            raise PlanningError(f"يوم حصة خارج المدى: {self.weekday}")
        if self.period not in range(1, MAX_PERIOD + 1):
            raise PlanningError(f"رقم حصة خارج المدى: {self.period}")


@dataclass(frozen=True, order=True)
class Session:
    day: date
    period: int


@dataclass(frozen=True)
class Item:
    id: str
    periods: int
    kind: str = "lesson"

    def __post_init__(self) -> None:
        if self.periods < 1:
            raise PlanningError(f"بند بلا حصص: {self.id}")
        if self.kind not in ITEM_KINDS:
            raise PlanningError(f"نوع بند غير معروف: {self.kind}")


@dataclass(frozen=True)
class Placement:
    item_id: str
    part: int  # رقم الحصة داخل البند، من 1
    parts: int
    session: Session


@dataclass(frozen=True)
class Plan:
    placements: tuple[Placement, ...]
    unplaced: tuple[str, ...]  # بنود لم يتسع لها الفصل، بترتيبها
    shortfall: int  # مجموع حصصها الناقصة

    def of(self, item_id: str) -> tuple[Placement, ...]:
        return tuple(p for p in self.placements if p.item_id == item_id)

    def span(self, item_id: str) -> tuple[date, date] | None:
        days = [p.session.day for p in self.of(item_id)]
        return (min(days), max(days)) if days else None


@dataclass(frozen=True)
class Move:
    item_id: str
    before: tuple[date, date] | None
    after: tuple[date, date] | None


def teaching_days(term: Term, extra_closures: Iterable[Closure] = ()) -> list[date]:
    """أيام دوام الفصل بعد استثناء كل المغلقات، مرتبة."""
    closures = (*term.closures, *extra_closures)
    out: list[date] = []
    day = term.start
    while day <= term.end:
        if day.weekday() in term.weekdays and not any(c.covers(day) for c in closures):
            out.append(day)
        day += timedelta(days=1)
    return out


def sessions(term: Term, slots: Collection[Slot], extra_closures: Iterable[Closure] = ()) -> list[Session]:
    """حصص الشعبة الفعلية في الفصل: كل يوم تدريس في كل خانة أسبوعية تطابق يومه، مرتبة بالتاريخ ثم الحصة."""
    by_weekday: dict[int, set[int]] = {}
    for slot in slots:
        by_weekday.setdefault(slot.weekday, set()).add(slot.period)
    return [
        Session(day, period)
        for day in teaching_days(term, extra_closures)
        for period in sorted(by_weekday.get(day.weekday(), ()))
    ]


def _check_items(items: Iterable[Item]) -> list[Item]:
    items = list(items)
    repeated = sorted(k for k, n in Counter(i.id for i in items).items() if n > 1)
    if repeated:
        raise PlanningError(f"بنود مكررة: {', '.join(repeated)}")
    return items


def _place(items: list[Item], free: list[Session], done: dict[str, int]) -> Plan:
    """يستهلك الحصص الحرة بالترتيب؛ البند الذي لا تكفيه الحصص المتبقية وكل ما بعده يُبلَّغ به ولا يوضع جزئيًا."""
    placements: list[Placement] = []
    unplaced: list[str] = []
    shortfall = 0
    cursor = 0
    for item in items:
        need = item.periods - done.get(item.id, 0)
        if need <= 0:
            continue
        if unplaced or cursor + need > len(free):
            unplaced.append(item.id)
            shortfall += need
            continue
        first = item.periods - need
        for offset in range(need):
            placements.append(Placement(item.id, first + offset + 1, item.periods, free[cursor + offset]))
        cursor += need
    return Plan(tuple(placements), tuple(unplaced), shortfall)


def allocate(items: Iterable[Item], free: Collection[Session]) -> Plan:
    """يوزّع البنود بترتيبها على الحصص بالتتابع."""
    return _place(_check_items(items), sorted(free), {})


def reflow(
    items: Iterable[Item],
    term: Term,
    slots: Collection[Slot],
    previous: Plan,
    today: date,
    lost: Collection[date] = (),
    extra_closures: Iterable[Closure] = (),
) -> Plan:
    """يعيد الخطة من `today`: حصص ما قبله تبقى كما هي، وما بعده يُعاد توزيعه بعد استثناء الأيام الضائعة.

    البند الذي بدأ قبل `today` ولم يكتمل يتابع من الجزء التالي له.
    """
    items = _check_items(items)
    kept = tuple(p for p in previous.placements if p.session.day < today)
    done = Counter(p.item_id for p in kept)
    lost_closures = [Closure(d, d, "other", "يوم ضائع") for d in lost]
    free = [s for s in sessions(term, slots, [*extra_closures, *lost_closures]) if s.day >= today]
    tail = _place(items, free, dict(done))
    return Plan((*kept, *tail.placements), tail.unplaced, tail.shortfall)


def moves(before: Plan, after: Plan, items: Iterable[Item]) -> list[Move]:
    """البنود التي تغيّر مداها بين خطتين."""
    out = []
    for item in items:
        a, b = before.span(item.id), after.span(item.id)
        if a != b:
            out.append(Move(item.id, a, b))
    return out


def load_terms(path: Path | None = None) -> dict[str, Term]:
    """فصول ملف التقويم بمعرّفاتها."""
    data = json.loads((path or DATA_DIR / "calendar_2026_2027.json").read_text(encoding="utf-8"))
    weekdays = tuple(WEEKDAYS[w] for w in data.get("weekdays", ())) or DEFAULT_WEEKDAYS
    terms: dict[str, Term] = {}
    for raw in data["terms"]:
        closures = tuple(
            Closure(
                date.fromisoformat(c["start"]),
                date.fromisoformat(c["end"]),
                c.get("kind", "other"),
                c.get("label", ""),
            )
            for c in raw.get("closures", ())
        )
        term = Term(
            raw["id"],
            raw["name"],
            date.fromisoformat(raw["start"]),
            date.fromisoformat(raw["end"]),
            closures,
            weekdays,
        )
        for c in closures:
            if c.start < term.start or c.end > term.end:
                raise PlanningError(f"إغلاق خارج حدّ الفصل {term.id}: {c.label}")
        terms[term.id] = term
    return terms
