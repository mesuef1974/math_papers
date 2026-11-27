"""مهام Celery لتطبيق planning. idempotent: الناتج مفتاحه مشتق من مدخلاته، فإعادة التنفيذ بعد موت العامل تجد الملف جاهزًا."""

from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model

from .services import build_class_pack, build_period_deck_file


@shared_task(name="planning.build_period_deck")
def build_period_deck_task(course: str, lesson: str, k: int, owner_id: int | None = None) -> str:
    """يبني عرض الحصة (بتحضير المعلم `owner_id` إن أُعطي) ويضعه في التخزين ويعيد مفتاحه؛ الفشل يُسجَّل في التخزين فتقرؤه
    الحالة."""
    owner = None if owner_id is None else get_user_model().objects.get(pk=owner_id)
    return build_period_deck_file(course, lesson, k, owner=owner)


@shared_task(name="planning.build_class_pack")
def build_class_pack_task(owner_id: int, course: str, lesson: str, section: str, date: str = "") -> str:
    """يبني الحزمة العلاجية لشعبة المعلم في درس ويعيد مفتاح ملفها؛ لا مسار يستدعيها بعد (M2.3).

    تطبع في العامل صفحة الطباعة التي يقدّمها الويب، فقبل استدعائها من مسار يلزم للعامل `PDF_RENDER_BASE_URL` و`REDIS_URL`
    و`SECRET_KEY` و`ASSETS_*` كالويب."""
    owner = get_user_model().objects.get(pk=owner_id)
    return build_class_pack(owner, course, lesson, section, date)
