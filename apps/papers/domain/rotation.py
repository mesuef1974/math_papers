"""تدوير الدروس في النموذج ب: كل مجموعة دروس في جدول المواصفات تتبادل دروسها بين خاناتها.

الخانة تحتفظ بنوعها ودرجتها ومستواها، فيبقى توزيع الدرجات والأعماق كما في أ، ويتغير الدرس الذي تقيسه.
الترتيب: تغطية دروس المجموعة كلها أولًا، ثم أكبر عدد من الخانات بدرس غير درسها في أ. فروع السؤال الواحد بدروس مختلفة.
خانة لا يقيس مستواها درس آخر من المجموعة تبقى على درسها. منطق نقي بلا قاعدة بيانات، حتمي من مولّد الأعداد.
"""

from __future__ import annotations

import itertools
import random
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RotationSlot:
    key: tuple[int, int]  # (رقم السؤال، ترتيب الفرع)
    group: str
    lesson: str
    kind: str
    level: str
    graph: bool


Fits = Callable[[str, str, str, bool], bool]  # (الدرس، النوع، المستوى، الرسم) → هل له صيغة مطابقة


def rotate(slots: Sequence[RotationSlot], fits: Fits, rng: random.Random) -> dict[tuple[int, int], str]:
    """درس كل خانة في النموذج ب. الخانة بلا مجموعة تبقى على درسها."""
    result = {slot.key: slot.lesson for slot in slots}
    groups: dict[str, list[RotationSlot]] = defaultdict(list)
    for slot in slots:
        if slot.group:
            groups[slot.group].append(slot)
    for name in sorted(groups):
        result.update(_rotate_group(groups[name], fits, rng))
    return result


def _rotate_group(slots: list[RotationSlot], fits: Fits, rng: random.Random) -> dict[tuple[int, int], str]:
    lessons = list(dict.fromkeys(slot.lesson for slot in slots))
    options = []
    for slot in slots:
        fitting = [
            code for code in lessons if code == slot.lesson or fits(code, slot.kind, slot.level, slot.graph)
        ]
        options.append(fitting)
    best: list[tuple[str, ...]] = []
    best_score = (-1, -1)
    for choice in itertools.product(*options):
        if not _parts_distinct(slots, choice):
            continue
        score = (len(set(choice)), sum(code != slot.lesson for code, slot in zip(choice, slots, strict=True)))
        if score > best_score:
            best_score, best = score, [choice]
        elif score == best_score:
            best.append(choice)
    if not best:  # لا ترتيب يفرّق فروع السؤال: يبقى أ
        return {slot.key: slot.lesson for slot in slots}
    chosen = rng.choice(best)
    return {slot.key: code for slot, code in zip(slots, chosen, strict=True)}


def _parts_distinct(slots: list[RotationSlot], choice: tuple[str, ...]) -> bool:
    seen: set[tuple[int, str]] = set()
    for slot, code in zip(slots, choice, strict=True):
        mark = (slot.key[0], code)
        if mark in seen:
            return False
        seen.add(mark)
    return True
