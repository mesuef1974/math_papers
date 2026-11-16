"""حزمة الإعدادات. تطبيق Celery يُحمَّل مع Django كي تُسجَّل المهام المشتركة (`shared_task`) عليه."""

from .celery import app as celery_app

__all__ = ("celery_app",)
