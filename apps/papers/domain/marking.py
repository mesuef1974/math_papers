"""توزيع درجة الفرع المقالي على بنود حله، على نسق دليل تقدير الدرجات: خطوات الطريقة ثم الجواب النهائي.

القواعد (قرار المالك 2026-11-14): أصغر وحدة نصف درجة، والجواب النهائي بند مستقل بدرجته، والخطوات المتجاورة
تُدمج في بند واحد إن زاد عددها على أنصاف درجات الطريقة. الأسئلة الموضوعية لا توزيع لها: درجتها لرمز الإجابة.
الحساب بأنصاف صحيحة فلا خطأ تقريب، ومجموع البنود يساوي درجة الفرع دائمًا.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

ESSAY = "essay"
HALVES_PER_MARK = 2
ANSWER_HALVES = 2  # درجة الدقة للجواب النهائي: درجة كاملة، ونصف درجة في فرع الدرجة الواحدة


@dataclass(frozen=True)
class MarkItem:
    """بند في جدول التوزيع: خطوة (أو خطوات متجاورة مدموجة) بدرجتها، أو الجواب النهائي (steps فارغة)."""

    steps: tuple[str, ...]
    halves: int
    final: bool = False

    @property
    def marks(self) -> float:
        return self.halves / HALVES_PER_MARK

    def as_dict(self) -> dict:
        return {"steps": list(self.steps), "marks": self.marks, "final": self.final}


def _groups(steps: Sequence[str], count: int) -> list[tuple[str, ...]]:
    """يقسم الخطوات إلى مجموعات متجاورة عددها count؛ الزائد يذهب إلى المجموعات الأولى فتبقى الخلاصة بندًا وحدها."""
    size, extra = divmod(len(steps), count)
    groups, start = [], 0
    for index in range(count):
        end = start + size + (1 if index < extra else 0)
        groups.append(tuple(steps[start:end]))
        start = end
    return groups


def allocate(steps: Sequence[str], marks: int) -> tuple[MarkItem, ...]:
    """بنود التوزيع لفرع درجته marks. بلا درجة لا توزيع؛ وبلا خطوات الدرجة كلها للجواب النهائي.

    ما يبقى بعد درجة الجواب يُقسم على الخطوات بالتساوي بأنصاف الدرجات، والباقي للخطوات الأخيرة
    لأنها تحمل الاستنتاج.
    """
    if marks <= 0:
        return ()
    total = marks * HALVES_PER_MARK
    if not steps:
        return (MarkItem((), total, final=True),)
    answer = min(ANSWER_HALVES, total // 2)
    method = total - answer
    groups = _groups(steps, min(len(steps), method))
    base, extra = divmod(method, len(groups))
    first_raised = len(groups) - extra
    items = [
        MarkItem(group, base + (1 if index >= first_raised else 0)) for index, group in enumerate(groups)
    ]
    return (*items, MarkItem((), answer, final=True))


def marking(kind: str, steps: Sequence[str], marks: int) -> list[dict]:
    """التوزيع كما يُرسل مع الجزء: للمقالي ذي الدرجة فقط، وقائمة فارغة لغيره."""
    if kind != ESSAY:
        return []
    return [item.as_dict() for item in allocate(steps, marks)]
