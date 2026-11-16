"""مهام Celery لتطبيق planning. idempotent: الناتج مفتاحه مشتق من مدخلاته، فإعادة التنفيذ بعد موت العامل تجد الملف جاهزًا."""

from __future__ import annotations

from celery import shared_task

from .services import build_lesson_deck


@shared_task(name="planning.build_lesson_deck")
def build_lesson_deck_task(course_slug: str, lesson_code: str, period_minutes: int) -> str:
    """يبني عرض الدرس ويضعه في التخزين ويعيد مفتاحه؛ الفشل يُسجَّل في التخزين فتقرؤه الحالة."""
    return build_lesson_deck(course_slug, lesson_code, period_minutes)
