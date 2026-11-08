"""قراءات الأوراق."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet

from .models import (
    DEFAULT_EXAM_INSTRUCTIONS,
    DEFAULT_EXAM_MINUTES,
    DEFAULT_GRADE,
    DEFAULT_SUBJECT,
    DEFAULT_WORKSHEET_INSTRUCTIONS,
    PrintProfile,
    SavedPaper,
)

PROFILE_FIELDS = (
    "school",
    "teacher_name",
    "subject",
    "grade",
    "exam_minutes",
    "exam_instructions",
    "worksheet_instructions",
)


def print_profile(user: AbstractBaseUser) -> dict[str, Any]:
    """ترويسة المعلم، أو الافتراضيات إن لم يحفظ شيئًا بعد (لا كتابة عند القراءة)."""
    row = PrintProfile.objects.filter(user=user).first()
    if row is None:
        return {
            "school": "",
            "teacher_name": "",
            "subject": DEFAULT_SUBJECT,
            "grade": DEFAULT_GRADE,
            "exam_minutes": DEFAULT_EXAM_MINUTES,
            "exam_instructions": DEFAULT_EXAM_INSTRUCTIONS,
            "worksheet_instructions": DEFAULT_WORKSHEET_INSTRUCTIONS,
        }
    return {name: getattr(row, name) for name in PROFILE_FIELDS}


def saved_papers(user: AbstractBaseUser) -> QuerySet[SavedPaper]:
    """قائمة أوراق المعلم بلا لقطاتها (الأعمدة المختصرة تكفي القائمة)."""
    return SavedPaper.objects.filter(owner=user).defer("snapshot", "recipe")


def saved_paper(user: AbstractBaseUser, pk: int) -> SavedPaper | None:
    return SavedPaper.objects.filter(owner=user, pk=pk).first()
