"""مهام Celery لتطبيق planning. idempotent: الناتج مفتاحه مشتق من مدخلاته، فإعادة التنفيذ بعد موت العامل تجد الملف جاهزًا."""

from __future__ import annotations

from celery import shared_task

from .services import build_period_deck_file


@shared_task(name="planning.build_period_deck")
def build_period_deck_task(course: str, lesson: str, k: int) -> str:
    """يبني عرض الحصة ويضعه في التخزين ويعيد مفتاحه؛ الفشل يُسجَّل في التخزين فتقرؤه الحالة."""
    return build_period_deck_file(course, lesson, k)
