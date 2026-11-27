"""فهرس صيغ المولّدات كما تعلنها الشيفرة، وفجوات تغطية الأمثلة بها. نقي بلا Django."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass

from .generators import LEVEL_NAMES, REGISTRY, skill_example, variant_profile
from .item_bank import usable

MIN_FORMS = 2  # شرط انتهاء المرحلة 3 في docs/hybrid_practice_plan.md


@dataclass(frozen=True)
class FormSpec:
    course: str
    lesson: str
    name: str
    example: int | None
    level: str  # حروف المستويات التي تعطيها الصيغة بترتيب LEVEL_NAMES
    has_item: bool


def declared_forms() -> list[FormSpec]:
    """صيغ سجلّ الأوراق (REGISTRY) وحدها؛ «اكتشف الخطأ» لا تدخل الواجب."""
    found = []
    for (course, lesson), fns in sorted(REGISTRY.items()):
        for fn in fns:
            levels = variant_profile(fn)[0]
            found.append(
                FormSpec(
                    course,
                    lesson,
                    fn.__name__,
                    skill_example(course, lesson, fn.__name__),
                    "".join(level for level in LEVEL_NAMES if level in levels),
                    usable(fn),
                )
            )
    return found


@dataclass(frozen=True)
class Gap:
    lesson: str
    example: int
    forms: tuple[str, ...]  # الصيغ القائمة، وهي أقل من MIN_FORMS


def form_gaps(
    examples: Iterable[tuple[str, int]], forms: Mapping[tuple[str, int], Collection[str]]
) -> list[Gap]:
    """الأمثلة (درس، رقم) التي لا تبلغ صيغُها `MIN_FORMS`، بترتيب ورودها."""
    return [
        Gap(lesson, n, tuple(sorted(forms.get((lesson, n), ()))))
        for lesson, n in examples
        if len(forms.get((lesson, n), ())) < MIN_FORMS
    ]
