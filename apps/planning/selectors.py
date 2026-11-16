"""قراءة: ملف الدرس الشخصي من فهرس العاشر المشتق وسير الحصة المبني عليه. حتمي، بلا نص دليل ولا توكنز."""

from __future__ import annotations

from collections.abc import Collection

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet

from apps.knowledge.domain.grade10_index import Grade10Lesson
from apps.knowledge.selectors import grade10_index, grade10_lesson

from .domain.deck import Deck, LessonContent, build_deck
from .domain.feedback import ClassOutcome, Decision, decide
from .domain.strategies import (
    DEFAULT_PERIOD_MINUTES,
    Flow,
    LessonProfile,
    build_flow,
)
from .models import ClassOutcomeRecord, LessonRunRecord


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


def outcome_records(owner: AbstractBaseUser, section: str | None = None) -> QuerySet[ClassOutcomeRecord]:
    rows = ClassOutcomeRecord.objects.filter(owner=owner)
    return rows.filter(section=section) if section else rows


def outcome_of(record: ClassOutcomeRecord) -> ClassOutcome:
    return ClassOutcome(
        record.lesson_code, record.attempted, record.correct, record.pace, frozenset(record.obstacles)
    )


def decision_of(record: ClassOutcomeRecord) -> Decision:
    """القرار يُشتق دائمًا من السجل بالعتبات الحالية ولا يُخزَّن، فتعديل العتبات يسري على النتائج المحفوظة."""
    return decide(outcome_of(record))


def run_reports(owner: AbstractBaseUser, section: str | None = None) -> QuerySet[LessonRunRecord]:
    rows = LessonRunRecord.objects.filter(owner=owner)
    return rows.filter(section=section) if section else rows


def lesson_deck(
    code: str,
    content: LessonContent,
    period_minutes: int = DEFAULT_PERIOD_MINUTES,
    resources: Collection[str] = (),
) -> Deck:
    """عرض الدرس: الفهرس المشتق وسير الحصة من هنا، والنصوص والمقصوصات من `content` (خارج المستودع)."""
    lesson = grade10_lesson(code)
    if lesson is None:
        raise KeyError(f"درس غير موجود في الفهرس: {code}")
    flow = build_flow(period_minutes, profile_from_lesson(lesson), resources=resources)
    return build_deck(lesson, content, flow)
