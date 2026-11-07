"""قراءات المنهج."""

from __future__ import annotations

from django.db.models import QuerySet

from .models import Blueprint, Lesson


def lessons() -> QuerySet[Lesson]:
    return Lesson.objects.all()


def blueprints() -> QuerySet[Blueprint]:
    return Blueprint.objects.all()


def blueprint_with_items(slug: str) -> Blueprint | None:
    return Blueprint.objects.prefetch_related("items__lesson").filter(slug=slug).first()
