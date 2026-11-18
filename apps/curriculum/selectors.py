"""قراءات المنهج."""

from __future__ import annotations

from django.db.models import Count, QuerySet

from .models import AcademicCalendar, Blueprint, Course, Lesson, TermPlan


class UnknownCourseError(LookupError):
    pass


def courses() -> QuerySet[Course]:
    """كل المقررات بعدد دروسها، مرتبة بالصف فالمسار فالفصل فالطبعة.

    الترتيب صريح: Django يُسقط `Meta.ordering` من استعلام التجميع (GROUP BY)، فيعود الترتيب لقاعدة البيانات.
    """
    return Course.objects.annotate(lesson_count=Count("lessons")).order_by(
        "grade", "track", "semester", "edition"
    )


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


def calendar_data(year: str) -> dict:
    """تقويم سنة من جداوله بصيغة العقد (`CalendarData`) ليقرأه محرك التخطيط. `KeyError` لسنة بلا تقويم."""
    calendar = AcademicCalendar.objects.prefetch_related("terms__events").filter(year=year).first()
    if calendar is None:
        raise KeyError(f"لا تقويم للسنة {year}")
    return {
        "year": calendar.year,
        "weekdays": list(calendar.weekdays),
        "terms": [
            {
                "semester": term.semester,
                "start": term.start.isoformat(),
                "end": term.end.isoformat(),
                "closures": [
                    {"start": e.start.isoformat(), "end": e.end.isoformat(), "kind": e.kind, "label": e.label}
                    for e in term.events.all()
                ],
            }
            for term in calendar.terms.all()
        ],
    }


def term_plan_data(course_slug: str) -> tuple[Course, dict]:
    """الخطة الفصلية لمقرر من جداولها بصيغة العقد (`TermPlanData`)، مع مقررها. `KeyError` لمقرر بلا خطة."""
    plan = (
        TermPlan.objects.select_related("course")
        .prefetch_related("weeks__entries__lesson", "enrichments__lesson")
        .filter(course__slug=course_slug)
        .first()
    )
    if plan is None:
        raise KeyError(f"لا خطة فصلية للمقرر {course_slug}")
    window = None
    if plan.class_during_exams_start and plan.class_during_exams_end:
        window = {
            "start": plan.class_during_exams_start.isoformat(),
            "end": plan.class_during_exams_end.isoformat(),
        }
    examples: dict[str, list[int]] = {}
    for row in plan.enrichments.all():
        if row.example is not None:
            examples.setdefault(row.lesson.code, []).append(row.example)
    return plan.course, {
        "sessions_per_week": plan.sessions_per_week,
        "class_during_exams": window,
        "lost_days": list(plan.lost_days),
        "enrichment_lessons": sorted(r.lesson.code for r in plan.enrichments.all() if r.example is None),
        "enrichment_examples": {code: sorted(numbers) for code, numbers in examples.items()},
        "weeks": [
            {
                "n": week.number,
                "start": week.start.isoformat(),
                "end": week.end.isoformat(),
                "items": [
                    {
                        "kind": e.kind,
                        "periods": e.periods,
                        "lesson": e.lesson.code if e.lesson_id else None,
                        "unit": e.unit,
                        "scope": e.scope or None,
                    }
                    for e in week.entries.all()
                ],
            }
            for week in plan.weeks.all()
        ],
    }
