"""قراءة: ملف الدرس الشخصي من فهرس العاشر المشتق وسير الحصة المبني عليه. حتمي، بلا نص دليل ولا توكنز."""

from __future__ import annotations

from collections.abc import Collection

from apps.knowledge.domain.grade10_index import Grade10Lesson
from apps.knowledge.selectors import grade10_index, grade10_lesson

from .domain.strategies import (
    DEFAULT_PERIOD_MINUTES,
    Flow,
    LessonProfile,
    build_flow,
)


def profile_from_lesson(lesson: Grade10Lesson) -> LessonProfile:
    """بلوم من أهداف الدرس (غير المصنَّف لا يُحسب) وDOK من صفوف تحليل تمارينه؛ ما لم يُقرأ يبقى فارغًا فلا يُخمَّن."""
    return LessonProfile(
        bloom=frozenset(b for b in lesson.objectives_bloom if b != "unclassified"),
        dok=frozenset(row.dok for row in lesson.analysis),
    )


def lesson_profile(code: str) -> LessonProfile:
    lesson = grade10_lesson(code)
    if lesson is None:
        raise KeyError(f"درس غير موجود في الفهرس: {code}")
    return profile_from_lesson(lesson)


def lesson_flow(
    code: str,
    period_minutes: int = DEFAULT_PERIOD_MINUTES,
    resources: Collection[str] = (),
) -> Flow:
    return build_flow(period_minutes, lesson_profile(code), resources=resources)


def lesson_codes() -> list[str]:
    return [lesson.lesson for lesson in grade10_index().lessons]
