"""مهام Celery لتطبيق planning. idempotent: الناتج مفتاحه مشتق من مدخلاته، فإعادة التنفيذ بعد موت العامل تجد الملف جاهزًا."""

from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model

from . import package_build
from .services import build_period_deck_file, run_class_pack


@shared_task(name="planning.build_period_deck")
def build_period_deck_task(course: str, lesson: str, k: int, owner_id: int | None = None) -> str:
    """يبني عرض الحصة (بتحضير المعلم `owner_id` إن أُعطي) ويضعه في التخزين ويعيد مفتاحه؛ الفشل يُسجَّل في التخزين فتقرؤه
    الحالة."""
    owner = None if owner_id is None else get_user_model().objects.get(pk=owner_id)
    return build_period_deck_file(course, lesson, k, owner=owner)


@shared_task(name="planning.build_class_pack")
def build_class_pack_task(owner_id: int, course: str, lesson: str, section: str, date: str = "") -> str:
    """يبني الحزمة العلاجية لشعبة المعلم في درس ويعيد مفتاح ملفها، ويسجّل حالتها (يستدعيها مسار `remedial-packs`).

    تطبع في العامل صفحة الطباعة التي يقدّمها الويب، فيلزم للعامل `PDF_RENDER_BASE_URL` و`REDIS_URL`
    و`SECRET_KEY` و`ASSETS_*` كالويب."""
    return run_class_pack(owner_id, course, lesson, section, date)


@shared_task(name="planning.build_lesson_package")
def build_lesson_package_task(owner_id: int, course: str, lesson: str, k: int) -> str:
    """يبني الملف المضغوط لباقة الحصة (يستدعيها مسار `preps/…/package`). إعدادات العامل كالحزمة العلاجية."""
    return package_build.run(package_build.Scope(owner_id, course, lesson, k))
