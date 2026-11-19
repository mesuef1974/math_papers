"""مهام Celery لتطبيق planning. idempotent: الناتج مفتاحه مشتق من مدخلاته، فإعادة التنفيذ بعد موت العامل تجد الملف جاهزًا."""

from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model

from .services import build_period_deck_file


@shared_task(name="planning.build_period_deck")
def build_period_deck_task(course: str, lesson: str, k: int, owner_id: int | None = None) -> str:
    """يبني عرض الحصة (بتحضير المعلم `owner_id` إن أُعطي) ويضعه في التخزين ويعيد مفتاحه؛ الفشل يُسجَّل في التخزين فتقرؤه
    الحالة."""
    owner = None if owner_id is None else get_user_model().objects.get(pk=owner_id)
    return build_period_deck_file(course, lesson, k, owner=owner)
