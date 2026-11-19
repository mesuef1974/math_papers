"""أرقام كتاب الطالب لدرس بصياغتنا: صفحة كل مثال وتدريبات الكتاب عليه، تُضاف إلى ملف الدرس بلا مسّ أي نص.

المدخل مخرجات خط الاستخراج (أرقام فقط): صفحة بدء كل مثال في ملف الدليل (`examples.json`)، وجدول صفحة الملف → الصفحة المطبوعة
(`printed_pages.json`)، وربط التدريبات بالأمثلة (`exercise_links.json`). عمق مجموعة التمارين من مستوى قالب التمرين في الدرس نفسه
(K=1، A=2، R=3)، يُعرف القالب من مدى الأرقام في أول عنوانه («10-13»، «35 …»)، والتمرين بلا قالب أو بلا مستوى عمقه 2.
الدالة نقية وidempotent: لا تغيّر مدخلها، وتطبيقها مرتين كتطبيقها مرة.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

DOK = {"K": 1, "A": 2, "R": 3}
DEFAULT_DOK = 2
MAX_EXAMPLE = 20  # حد `ExerciseGroupData.example`
_LABEL_RANGE = re.compile(r"^\s*(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?(?!\d)")


def template_doks(templates: Iterable[Mapping[str, Any]]) -> dict[int, int]:
    """رقم التمرين → عمقه من قوالب الدرس. القالب الذي لا يبدأ عنوانه برقم (مراجعة سريعة...) ترقيمه غير ترقيم التمارين فيُهمل."""
    out: dict[int, int] = {}
    for template in templates:
        match = _LABEL_RANGE.match(template.get("label", ""))
        level = DOK.get(template.get("level", ""))
        if not match or level is None:
            continue
        first = int(match[1])
        last = int(match[2]) if match[2] else first
        for number in range(first, last + 1):
            out.setdefault(number, level)
    return out


def exercise_groups(
    links: Iterable[Mapping[str, Any]], doks: Mapping[int, int], examples: set[int]
) -> list[dict[str, Any]]:
    """صفوف `exercise_groups` مرتبة بالمثال ثم العمق؛ رابط إلى مثال ليس في الدرس أو بلا تدريبات يُهمل."""
    merged: dict[int, set[int]] = {}
    for row in links:
        if row["example"] in examples and row["example"] <= MAX_EXAMPLE:
            merged.setdefault(row["example"], set()).update(int(x) for x in row["exercises"])
    groups: list[dict[str, Any]] = []
    for example in sorted(merged):
        by_dok: dict[int, list[int]] = {}
        for number in sorted(merged[example]):
            by_dok.setdefault(doks.get(number, DEFAULT_DOK), []).append(number)
        groups += [{"example": example, "dok": dok, "exercises": by_dok[dok]} for dok in sorted(by_dok)]
    return groups


def _with_page(example: dict[str, Any], page: int | None) -> dict[str, Any]:
    if page is None:
        return dict(example)
    out: dict[str, Any] = {}
    for key, value in example.items():
        if key != "page":
            out[key] = value
        if key == "number":
            out["page"] = page  # موضعه بعد الرقم دائمًا، فالتشغيل الثاني لا يحرّك مفتاحًا
    return out


def annotate(
    lesson: Mapping[str, Any],
    pages: Mapping[int, int],
    links: Iterable[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """نسخة من ملف الدرس بـ `page` لكل مثال عُرفت صفحته وبـ `exercise_groups` من الروابط.

    `pages`: رقم المثال → صفحته المطبوعة (ما غاب يبقى كما كان). `links`: صفوف `{example, exercises}`، وNone أو ما لا ينتج
    مجموعة يترك `exercise_groups` كما كانت. المفتاح الجديد `exercise_groups` يوضع قبل `examples`، ولا يُمسّ حقل غير هذين.
    """
    examples = [_with_page(e, pages.get(e["number"])) for e in lesson.get("examples", [])]
    groups = (
        exercise_groups(links, template_doks(lesson.get("templates", [])), {e["number"] for e in examples})
        if links is not None
        else []
    )
    out: dict[str, Any] = {}
    for key, value in lesson.items():
        if key == "examples":
            if groups:
                out["exercise_groups"] = groups
            out[key] = examples
        elif key != "exercise_groups" or not groups:
            out[key] = value
    return out
