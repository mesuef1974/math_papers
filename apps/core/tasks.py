"""مهام Celery لتطبيق core."""

from __future__ import annotations

from celery import shared_task


@shared_task(name="core.ping")
def ping() -> str:
    """مهمة فحص تثبت أن الوسيط والعامل يعملان. بلا أثر جانبي، فتكرارها لا يغيّر شيئًا."""
    return "pong"
