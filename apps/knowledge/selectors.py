"""قراءة معرفة المنهج لتحضير الدروس والتقارير."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Sum

from .models import ExerciseTemplate


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
