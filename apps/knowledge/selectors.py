"""قراءة معرفة المنهج لتحضير الدروس والتقارير."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.db.models import Sum

from .domain.grade10_index import Grade10Index, Grade10Lesson
from .models import ExerciseTemplate

GRADE10_INDEX = Path(__file__).resolve().parent / "data" / "grade10_index.json"


@dataclass(frozen=True)
class CoverageRow:
    lesson: str
    level: str
    graph: bool
    templates: int  # عدد التمارين المستنتجة في الدليل
    generators: int  # عدد صيغ المولّدات المتاحة


def template_counts() -> dict[tuple[str, str, bool], int]:
    """(درس، مستوى، رسم) -> مجموع التمارين في القوالب."""
    totals: dict[tuple[str, str, bool], int] = {}
    rows = (
        ExerciseTemplate.objects.exclude(level="")
        .values("profile__lesson__code", "level", "representation")
        .annotate(n=Sum("count"))
    )
    for row in rows:
        key = (row["profile__lesson__code"], row["level"], "بياني" in row["representation"])
        totals[key] = totals.get(key, 0) + row["n"]
    return totals


def coverage() -> list[CoverageRow]:
    from apps.papers.domain.generators import variants

    result = []
    for (lesson, level, graph), count in sorted(template_counts().items()):
        result.append(CoverageRow(lesson, level, graph, count, len(variants(lesson, "essay", level, graph))))
    return result


@lru_cache(maxsize=1)
def grade10_index() -> Grade10Index:
    """فهرس العاشر المشتق من الملف المودَع (يُتحقق من مخططه عند أول قراءة)."""
    return Grade10Index(**json.loads(GRADE10_INDEX.read_text(encoding="utf-8")))


def grade10_lesson(code: str) -> Grade10Lesson | None:
    return next((lesson for lesson in grade10_index().lessons if lesson.lesson == code), None)
