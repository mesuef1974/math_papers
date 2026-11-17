"""قراءة الأصول."""

from __future__ import annotations

from django.db.models import QuerySet

from .models import Asset
from .storage import Storage, get_storage


def list_assets(course: str, lesson: str = "") -> QuerySet[Asset]:
    rows = Asset.objects.filter(course__slug=course).select_related("lesson", "course")
    return rows.filter(lesson__code=lesson) if lesson else rows


def asset_bytes(asset: Asset, storage: Storage | None = None) -> bytes:
    return (storage or get_storage()).get(asset.key)
