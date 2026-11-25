"""قراءات الأوراق."""

from __future__ import annotations

import random
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet

from apps.curriculum.courses import GRADE10_SLUG

from .domain.generators import ERROR_SPOTTING, REGISTRY
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
# بذور قياس مؤشرات الخطة: ثابتة ليعطي تشغيلان القيمة نفسها.
PLAN_METRIC_SEEDS = range(5)


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


def tagged_objective_formulas_pct() -> float | None:
    """نسبة الصيغ الموضوعية (لها مشتتات) التي توسم كل مشتتّ بنوع خطئه، على بذور ثابتة فالقيمة حتمية."""
    objective = tagged = 0
    for _, generators in sorted(REGISTRY.items()):
        for generate in generators:
            problems = [generate(random.Random(seed)) for seed in PLAN_METRIC_SEEDS]  # noqa: S311 — حتمية لا أمنية
            with_wrong = [p for p in problems if p.wrong]
            if not with_wrong:
                continue
            objective += 1
            tagged += all(len(p.wrong_kinds) == len(p.wrong) for p in with_wrong)
    return 100 * tagged / objective if objective else None


def lessons_with_error_spotting(course: str = GRADE10_SLUG) -> int:
    """عدد دروس المقرر التي لها صيغة «اكتشف الخطأ» واحدة على الأقل."""
    return len(
        {lesson for (registered, lesson), fns in ERROR_SPOTTING.items() if registered == course and fns}
    )


def saved_papers(user: AbstractBaseUser) -> QuerySet[SavedPaper]:
    """قائمة أوراق المعلم بلا لقطاتها (الأعمدة المختصرة تكفي القائمة)."""
    return SavedPaper.objects.filter(owner=user).select_related("course").defer("snapshot", "recipe")


def saved_paper(user: AbstractBaseUser, pk: int) -> SavedPaper | None:
    return SavedPaper.objects.filter(owner=user, pk=pk).select_related("course").first()
