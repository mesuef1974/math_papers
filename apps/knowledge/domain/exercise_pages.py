"""صفحات تمارين الدرس في كتاب الطالب: مديات `{first, last, page}` (أرقام فقط).

تُخزَّن مديات متتالية مرتبة لا تتداخل، فالدرس بخمسين تمرينًا على أربع صفحات أربعة صفوف. المصدر مخرج مرحلة استخراج
(`exercise_pages.json` في مجلد الكتاب خارج المستودع: لكل درس غلاف `{value, status}` قيمته المديات نفسها)، يكتبه
`build_course_index` في `index.json` و`write_book_numbers` في ملف الدرس، والمعتمد (`ok`) وحده ما لم يُطلب غيره.
التمرين بلا صفحة معروفة يبقى بلا صفحة: لا تخمين.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

MAX_EXERCISE = 99
MAX_PAGE = 999


class ExercisePages(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    first: int = Field(ge=1, le=MAX_EXERCISE)
    last: int = Field(ge=1, le=MAX_EXERCISE)
    page: int = Field(ge=1, le=MAX_PAGE)

    def model_post_init(self, __context: object) -> None:
        if self.last < self.first:
            raise ValueError(f"مدى تمارين مقلوب: {self.first}-{self.last}")


def check_ranges(ranges: list[ExercisePages]) -> list[ExercisePages]:
    """المديات مرتبة لا تتداخل، والصفحة لا تنقص بتزايد رقم التمرين (التمارين متتالية في الكتاب)."""
    for before, after in zip(ranges, ranges[1:], strict=False):
        if after.first <= before.last:
            raise ValueError(
                f"مديات تمارين متداخلة أو غير مرتبة: {before.first}-{before.last} و{after.first}-{after.last}"
            )
        if after.page < before.page:
            raise ValueError(f"صفحة التمرين {after.first} قبل صفحة التمرين {before.last}")
    return ranges


def page_map(ranges: Iterable[ExercisePages | Mapping[str, int]]) -> dict[int, int]:
    """رقم التمرين → صفحته المطبوعة."""
    out: dict[int, int] = {}
    for r in ranges:
        first, last, page = (
            (r["first"], r["last"], r["page"]) if isinstance(r, Mapping) else (r.first, r.last, r.page)
        )
        for number in range(first, last + 1):
            out[number] = page
    return out


def compress(pages: Mapping[int, int]) -> list[dict[str, int]]:
    """رقم التمرين → صفحته، إلى مديات `{first, last, page}`: يقطع المدى تغيّر الصفحة أو فجوة في الأرقام."""
    out: list[dict[str, int]] = []
    for number in sorted(pages):
        page = pages[number]
        if out and out[-1]["page"] == page and out[-1]["last"] == number - 1:
            out[-1]["last"] = number
        else:
            out.append({"first": number, "last": number, "page": page})
    return out


def accepted_ranges(record: Any, accepted: Iterable[str] = ("ok",)) -> list[dict[str, int]] | None:
    """مديات درس من غلاف المرحلة `{value, status}` إن قُبلت حالته وصحّ شكلها، وإلا None (يبقى ما في الملف)."""
    if not isinstance(record, Mapping) or record.get("status") not in tuple(accepted):
        return None
    try:
        ranges = check_ranges([ExercisePages(**r) for r in record.get("value") or []])
    except (TypeError, ValueError):
        return None
    return [r.model_dump() for r in ranges] or None
