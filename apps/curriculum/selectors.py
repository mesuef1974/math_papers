"""قراءات المنهج."""

from __future__ import annotations

from django.db.models import Count, QuerySet

from .models import Blueprint, Course, Lesson


class UnknownCourseError(LookupError):
    pass


def courses() -> QuerySet[Course]:
    """كل المقررات بعدد دروسها، مرتبة بالصف فالمسار فالفصل."""
    return Course.objects.annotate(lesson_count=Count("lessons"))


def current_course() -> Course | None:
    """المقرر الذي تفترضه المسارات حين لا يُحدَّد مقرر."""
    return Course.objects.filter(is_current=True).first()


def course_by_slug(slug: str = "") -> Course:
    """مقرر بمعرّفه، والفارغ هو المقرر الحالي."""
    course = Course.objects.filter(slug=slug).first() if slug else current_course()
    if course is None:
        raise UnknownCourseError(slug)
    return course


def lessons(course: Course | None = None) -> QuerySet[Lesson]:
    """دروس مقرر؛ بلا مقرر تُعاد دروس المقرر الحالي."""
    course = course or current_course()
    return Lesson.objects.filter(course=course) if course else Lesson.objects.none()


def blueprints() -> QuerySet[Blueprint]:
    return Blueprint.objects.all()


def blueprint_with_items(slug: str) -> Blueprint | None:
    return Blueprint.objects.prefetch_related("items__lesson__course").filter(slug=slug).first()
