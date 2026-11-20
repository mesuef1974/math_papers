"""قراءة معرفة المنهج لتحضير الدروس والتقارير."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Sum

from apps.curriculum.courses import GRADE12_SLUG

from .domain.contract import SCHEMA_VERSION, source_hash, source_slugs
from .domain.course_index import CourseIndex, LessonIndex
from .domain.schemas import lesson_sort_key
from .models import ExerciseGroup, ExerciseTemplate, LessonProfile, WorkedExample


@dataclass(frozen=True)
class CoverageRow:
    lesson: str
    level: str
    graph: bool
    templates: int  # عدد التمارين المستنتجة في الدليل
    generators: int  # عدد صيغ المولّدات المتاحة


def template_counts(course: str = GRADE12_SLUG) -> dict[tuple[str, str, bool], int]:
    """(درس، مستوى، رسم) -> مجموع التمارين في قوالب مقرر واحد."""
    totals: dict[tuple[str, str, bool], int] = {}
    rows = (
        ExerciseTemplate.objects.filter(profile__lesson__course__slug=course)
        .exclude(level="")
        .values("profile__lesson__code", "level", "representation")
        .annotate(n=Sum("count"))
    )
    for row in rows:
        key = (row["profile__lesson__code"], row["level"], "بياني" in row["representation"])
        totals[key] = totals.get(key, 0) + row["n"]
    return totals


def coverage(course: str = GRADE12_SLUG) -> list[CoverageRow]:
    from apps.papers.domain.generators import variants

    result = []
    for (lesson, level, graph), count in sorted(template_counts(course).items()):
        result.append(
            CoverageRow(lesson, level, graph, count, len(variants(lesson, "essay", level, graph, course)))
        )
    return result


def course_index(course: str) -> CourseIndex:
    """فهرس المقرر من جداوله كما حمّلها المحمِّل الواحد، من فهرسه المشتق `index.json` (كالعاشر) أو من دروسه بصياغتنا
    (كالثاني عشر، قرار المالك 2026-11-20)؛ الجداول مصدر القراءة الوحيد، وما لم تحمله الصياغة من أرقام الدليل فارغ.

    `KeyError` لمقرر لم يُحمَّل أو بلا دروس.
    """
    if not LessonProfile.objects.filter(lesson__course__slug=course).exists():
        raise KeyError(f"لا فهرس محمَّل للمقرر {course}")
    return course_index_from_tables(course)


def lesson_index(course: str, code: str) -> LessonIndex | None:
    """سجل درس في فهرس مقرره؛ None إن غاب الدرس أو لم يكن للمقرر فهرس مشتق."""
    try:
        lessons = course_index(course).lessons
    except KeyError:
        return None
    return next((lesson for lesson in lessons if lesson.lesson == code), None)


def example_page(course: str, lesson: str, number: int) -> int | None:
    """صفحة المثال المطبوعة في كتاب الطالب كما حمّلها المحمِّل؛ None إن غاب المثال أو صفحته."""
    return (
        WorkedExample.objects.filter(
            profile__lesson__course__slug=course, profile__lesson__code=lesson, number=number
        )
        .values_list("page", flat=True)
        .first()
    )


def example_numbers(course: str) -> dict[str, list[int]]:
    """أرقام أمثلة كل درس في مقرر من جداوله: من فهرسه المشتق أو من دروس المعرفة بصياغتنا، أيهما حمّله المحمِّل."""
    numbers: dict[str, list[int]] = {}
    rows = WorkedExample.objects.filter(profile__lesson__course__slug=course).order_by("number")
    for code, number in rows.values_list("profile__lesson__code", "number"):
        numbers.setdefault(code, []).append(number)
    return numbers


def example_exercises(course: str, lesson: str, number: int) -> list[int]:
    """أرقام تدريبات الكتاب التي تتدرّب على المثال (جدول «تحليل التمارين» كما حمّله المحمِّل)؛ فارغة إن لم تُعرف.

    صفوف `try` وحدها: تمارين قسم «تمارين» (`practice`) للتحضير، ولا تدخل مصدر الجزء في الأوراق."""
    groups = ExerciseGroup.objects.filter(
        profile__lesson__course__slug=course,
        profile__lesson__code=lesson,
        example=number,
        kind=ExerciseGroup.Kind.TRY,
    ).values_list("exercises", flat=True)
    return sorted({n for group in groups for n in group})


def course_index_from_tables(course: str) -> CourseIndex:
    """فهرس مقرر مشتقًّا من الجداول التي حمّلها المحمِّل الواحد: يطابق الملف المودَع حين يكون المقرر محمَّلًا."""
    profiles = (
        LessonProfile.objects.filter(lesson__course__slug=course)
        .select_related("lesson")
        .prefetch_related("standards", "practices", "objectives", "examples", "exercise_groups")
    )
    lessons = []
    for profile in sorted(profiles, key=lambda p: lesson_sort_key(p.lesson.code)):
        lessons.append(
            {
                "lesson": profile.lesson.code,
                "unit": profile.lesson.unit,
                "standards": sorted(s.code for s in profile.standards.all()),
                "practices": sorted(p.code for p in profile.practices.all()),
                "objectives_bloom": [o.bloom for o in profile.objectives.all()],
                "examples": [
                    {"n": e.number, "page": e.page, "representations": e.representations}
                    for e in profile.examples.all()
                ],
                "analysis": [
                    {"example": g.example, "dok": g.dok, "exercises": g.exercises, "kind": g.kind}
                    for g in profile.exercise_groups.all()
                ],
                "exercises_total": profile.exercises_total or 0,
                "task_guide": (
                    {"basic": profile.task_basic, "advanced": profile.task_advanced}
                    if profile.task_basic and profile.task_advanced
                    else None
                ),
                "quiz_depths": profile.quiz_depths,
                "vocabulary": {"new": profile.vocab_new or 0, "review": profile.vocab_review or 0},
            }
        )
    return CourseIndex(lessons=lessons)


def knowledge_state() -> dict[str, str]:
    """حالة كل مقرر ذي مصدر: ok (آخر إصدار يطابق ملفات المصدر) أو stale (تغيّرت الملفات بلا تحميل) أو unloaded."""
    from apps.curriculum.models import Course

    state = {}
    for slug in source_slugs():
        course = Course.objects.filter(slug=slug).first()
        release = course.knowledge_releases.first() if course else None
        if release is None:
            state[slug] = "unloaded"
        elif release.schema_version != SCHEMA_VERSION or release.content_hash != source_hash(slug):
            state[slug] = "stale"
        else:
            state[slug] = "ok"
    return state
