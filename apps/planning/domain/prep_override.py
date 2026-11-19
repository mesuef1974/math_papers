"""تعديل المعلم لتحضير حصص درس (`PeriodPrepOverride`): مخطط JSON مقيَّد وتحويله إلى مدخلات الاشتقاق، بلا Django.

الشكل المحفوظ (لدرس واحد ولمعلم واحد؛ كل مفتاح اختياري، والغائب يعني المشتق):

    {"allocation": [[1, 2], [3], []],
     "periods": {"2": {"strategies": {"guided": "think-pair-share"}, "removed": [14, 15]}}}

- `allocation`: أمثلة كل حصة من حصص الدرس بترتيبها. يحفظ قواعد `allocate`: الأمثلة الأساسية كلها بترتيبها، ومن مثال إلى
  ثلاثة لكل حصة قبل الأخيرة، والأخيرة بلا مثال؛ فنقل مثال بين حصتين تحريك حدٍّ بين حصتين متجاورتين.
- `periods`: لكل حصة (`k` نصًّا) استراتيجيات اختارها لمراحل من `stage_options`، وتمارين حذفها من تدريباتها.

التعديل يُطبَّق داخل الاشتقاق (`build_prep(teacher=…)`) لا بعده، ثم تُعاد المعايير؛ والخدمة ترفض حفظ ما يُفشل معيارًا حاجبًا.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from .calendar_engine import PlanningError
from .prep import MAX_OBJECTIVES, STAGE_NAMES, TeacherEdit, stage_options
from .strategies import Strategy

MAX_REMOVED = 40  # سقف التمارين المحذوفة في حصة: حدّ للمدخل لا قاعدة تربوية


class OverrideError(PlanningError):
    """تعديل لا يطابق المخطط أو قواعد التوزيع والمكتبة؛ الرسالة بالعربية للمعلم."""


@dataclass(frozen=True)
class LessonOverride:
    allocation: tuple[tuple[int, ...], ...] | None = None
    periods: Mapping[int, TeacherEdit] = field(default_factory=dict)

    def edit_for(self, k: int, default: Sequence[Sequence[int]]) -> TeacherEdit:
        base = self.periods.get(k, TeacherEdit())
        moved = self.allocation is not None and tuple(map(tuple, default)) != self.allocation
        return TeacherEdit(allocation=moved, strategies=base.strategies, removed=base.removed)

    def groups(self, default: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
        return self.allocation if self.allocation is not None else tuple(map(tuple, default))


def _ints(value: object, where: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in value):
        raise OverrideError(f"{where}: قائمة أعداد صحيحة")
    return tuple(value)


def _allocation(value: object, examples: Sequence[int], n: int) -> tuple[tuple[int, ...], ...]:
    if not isinstance(value, list) or len(value) != n:
        raise OverrideError(f"التوزيع: {n} حصص للدرس")
    groups = tuple(_ints(g, f"أمثلة الحصة {i}") for i, g in enumerate(value, start=1))
    if groups[-1]:
        raise OverrideError("الحصة الأخيرة للتمايز والتقويم بلا مثال جديد")
    for i, g in enumerate(groups[:-1], start=1):
        if not 1 <= len(g) <= MAX_OBJECTIVES:
            raise OverrideError(f"الحصة {i}: من مثال إلى {MAX_OBJECTIVES} أمثلة")
    if tuple(x for g in groups for x in g) != tuple(examples):
        raise OverrideError("التوزيع يحفظ أمثلة الدرس كلها بترتيبها: يُنقل مثال بين حصتين متجاورتين فقط")
    return groups


def _period(value: object, k: int, library: Sequence[Strategy]) -> TeacherEdit:
    if not isinstance(value, dict) or set(value) - {"strategies", "removed"}:
        raise OverrideError(f"الحصة {k}: المفاتيح strategies وremoved فقط")
    chosen = value.get("strategies", {})
    if not isinstance(chosen, dict):
        raise OverrideError(f"الحصة {k}: الاستراتيجيات قاموس مرحلة → استراتيجية")
    for stage, slug in chosen.items():
        if stage not in STAGE_NAMES:
            raise OverrideError(f"الحصة {k}: مرحلة غير معروفة {stage}")
        if not isinstance(slug, str) or slug not in {s.slug for s in stage_options(library, stage)}:
            raise OverrideError(f"الحصة {k}: الاستراتيجية {slug} لا تصلح للمرحلة {stage}")
    removed = _ints(value.get("removed", []), f"الحصة {k}: التمارين المحذوفة")
    if len(removed) > MAX_REMOVED or any(x < 1 for x in removed):
        raise OverrideError(f"الحصة {k}: تمارين محذوفة غير صالحة")
    return TeacherEdit(strategies=dict(sorted(chosen.items())), removed=frozenset(removed))


def parse_override(
    data: object, *, examples: Sequence[int], n: int, library: Sequence[Strategy]
) -> LessonOverride:
    """يتحقق من الشكل المحفوظ لدرس حصصه `n` وأمثلته الأساسية `examples` بترتيبها، ويعيده مدخلات للاشتقاق."""
    if not isinstance(data, dict) or set(data) - {"allocation", "periods"}:
        raise OverrideError("التعديل: المفاتيح allocation وperiods فقط")
    allocation = None if data.get("allocation") is None else _allocation(data["allocation"], examples, n)
    raw = data.get("periods", {})
    if not isinstance(raw, dict):
        raise OverrideError("الحصص: قاموس رقم الحصة → تعديلها")
    periods: dict[int, TeacherEdit] = {}
    for key, value in raw.items():
        if not (isinstance(key, str) and key.isdigit() and 1 <= int(key) <= n):
            raise OverrideError(f"رقم حصة غير صالح: {key}")
        periods[int(key)] = _period(value, int(key), library)
    return LessonOverride(allocation=allocation, periods=periods)


def dump_override(override: LessonOverride, default: Sequence[Sequence[int]]) -> dict:
    """الشكل القانوني للحفظ: ما يساوي المشتق يُسقط، فالتعديل الذي لا يغيّر شيئًا قاموس فارغ (ويُحذف سجله)."""
    out: dict = {}
    if override.allocation is not None and override.allocation != tuple(map(tuple, default)):
        out["allocation"] = [list(g) for g in override.allocation]
    periods = {}
    for k in sorted(override.periods):
        edit = override.periods[k]
        entry: dict = {}
        if edit.strategies:
            entry["strategies"] = dict(sorted(edit.strategies.items()))
        if edit.removed:
            entry["removed"] = sorted(edit.removed)
        if entry:
            periods[str(k)] = entry
    if periods:
        out["periods"] = periods
    return out


def unknown_removed(removed: Iterable[int], available: Iterable[int]) -> tuple[int, ...]:
    """تمارين محذوفة ليست من تمارين أمثلة الحصة: تُرفض فلا يحمل التعديل أرقامًا لا معنى لها."""
    return tuple(sorted(set(removed) - set(available)))
