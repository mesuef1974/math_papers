"""كتابة جداول المنهج من العقد القانوني: المصادر وجداول المواصفات والخطة الفصلية والاختبارات السابقة والتغطية والتقويم.

يستدعيها المحمِّل الواحد (`apps.knowledge.services.load_contract` و`load_all`) داخل معاملته. كلها idempotent: التشغيل
الثاني على العقد نفسه لا يكتب صفًا، و`changed` يعدّ ما تغيّر فعلًا. ما ليس في العقد لا يُمسّ (لا حذف لمصدر أو جدول غاب).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from django.db import models

from apps.knowledge.domain.sources import (
    CalendarData,
    CoverageData,
    PastExamData,
    SlotData,
    SourceData,
    TermPlanData,
)

from .models import (
    AcademicCalendar,
    Blueprint,
    BlueprintItem,
    CalendarEvent,
    CalendarTerm,
    Course,
    Lesson,
    PastExam,
    PastExamItem,
    PlanEnrichment,
    PlanEntry,
    PlanWeek,
    ResourceCoverage,
    SourceDocument,
    TermPlan,
)


class OwnerError(ValueError):
    """صف بالمعرّف نفسه يملكه مقرر آخر: معرّفات الجداول والاختبارات فريدة في المنصة كلها."""


def _update(row: models.Model, wanted: dict[str, Any]) -> bool:
    """يكتب الحقول المختلفة فقط؛ يعيد هل تغيّر شيء."""
    if all(getattr(row, key) == value for key, value in wanted.items()):
        return False
    for key, value in wanted.items():
        setattr(row, key, value)
    row.save()
    return True


def _owned(
    model: type[models.Model], slug: str, course: Course, wanted: dict[str, Any], changed: Counter, tag: str
):
    """صف مفتاحه معرّف فريد عامًّا ويملكه مقرر: ينشئه أو يحدّثه، ويرفض معرّفًا يملكه مقرر آخر."""
    row = model.objects.filter(slug=slug).first()
    if row is None:
        changed[tag] += 1
        return model.objects.create(slug=slug, course=course, **wanted)
    if row.course_id != course.pk:
        raise OwnerError(f"{slug} يملكه مقرر آخر غير {course.slug}")
    if _update(row, wanted):
        changed[tag] += 1
    return row


def sync_sources(
    course: Course, sources: Iterable[SourceData], changed: Counter
) -> dict[str, SourceDocument]:
    """ملفات المقرر المصدرية → `SourceDocument`؛ يعيد كل مصادر المقرر بمعرّفاتها (ومنها ما سُجّل قبل)."""
    existing = {row.slug: row for row in SourceDocument.objects.filter(course=course)}
    for data in sources:
        wanted = {**data.model_dump(exclude={"slug", "digest"}), "sha256": data.sha256}
        row = existing.get(data.slug)
        if row is None:
            existing[data.slug] = SourceDocument.objects.create(course=course, slug=data.slug, **wanted)
            changed["sources"] += 1
        elif _update(row, wanted):
            changed["sources"] += 1
    return existing


def _source(sources: dict[str, SourceDocument], slug: str | None) -> SourceDocument | None:
    return sources[slug] if slug else None


def sync_slots(
    model: type[models.Model],
    owner: dict[str, Any],
    rows: Sequence[SlotData],
    lessons: dict[str, Lesson],
    changed: Counter,
    tag: str,
    extra: Sequence[str] = (),
) -> None:
    """خانات جدول مواصفات أو اختبار سابق: ينشئ ويحدّث بمفتاح (السؤال، الموضع) ويحذف الخانة الزائدة."""
    current = {(row.question_number, row.position): row for row in model.objects.filter(**owner)}
    for data in rows:
        slot = (data.question_number, data.position)
        wanted = {
            "lesson_id": lessons[data.lesson].pk,
            "kind": data.kind,
            "marks": data.marks,
            "level": data.level,
            "needs_graph": data.needs_graph,
            **{name: getattr(data, name) for name in extra},
        }
        row = current.pop(slot, None)
        if row is None:
            model.objects.create(**owner, question_number=slot[0], position=slot[1], **wanted)
            changed[tag] += 1
        elif _update(row, wanted):
            changed[tag] += 1
    if current:
        model.objects.filter(pk__in=[row.pk for row in current.values()]).delete()
        changed[tag] += len(current)


def sync_blueprint(
    data, course: Course, lessons: dict[str, Lesson], sources: dict, changed: Counter
) -> Blueprint:
    """جدول مواصفات من العقد (`BlueprintData`) → `Blueprint` وخاناته."""
    wanted = data.model_dump(exclude={"slug", "items", "source"})
    wanted["source"] = _source(sources, data.source)
    blueprint = _owned(Blueprint, data.slug, course, wanted, changed, "blueprints")
    sync_slots(BlueprintItem, {"blueprint": blueprint}, data.items, lessons, changed, "blueprint_items")
    return blueprint


def sync_past_exam(
    data: PastExamData, course: Course, lessons: dict[str, Lesson], sources: dict, changed: Counter
) -> PastExam:
    wanted = data.model_dump(exclude={"slug", "items", "source"})
    wanted["source"] = _source(sources, data.source)
    exam = _owned(PastExam, data.slug, course, wanted, changed, "past_exams")
    sync_slots(PastExamItem, {"exam": exam}, data.items, lessons, changed, "past_exam_items", extra=("dok",))
    return exam


def sync_coverage(data: CoverageData, lessons: dict[str, Lesson], sources: dict, changed: Counter) -> None:
    source = sources[data.source]
    current = {row.lesson_id: row for row in ResourceCoverage.objects.filter(source=source)}
    for item in data.lessons:
        lesson = lessons[item.lesson]
        wanted = item.model_dump(exclude={"lesson"})
        row = current.pop(lesson.pk, None)
        if row is None:
            ResourceCoverage.objects.create(source=source, lesson=lesson, **wanted)
            changed["coverage"] += 1
        elif _update(row, wanted):
            changed["coverage"] += 1
    if current:
        ResourceCoverage.objects.filter(pk__in=[row.pk for row in current.values()]).delete()
        changed["coverage"] += len(current)


def _plan_shape(plan: TermPlan) -> tuple:
    """صورة الخطة المخزنة للمقارنة بالعقد: الأسابيع وبنودها والإثرائي."""
    weeks = tuple(
        (
            week.number,
            week.start,
            week.end,
            tuple(
                (e.kind, e.periods, e.lesson.code if e.lesson_id else None, e.unit, e.scope or None)
                for e in week.entries.all()
            ),
        )
        for week in plan.weeks.prefetch_related("entries__lesson")
    )
    extras = tuple(sorted((x.lesson.code, x.example or 0) for x in plan.enrichments.select_related("lesson")))
    return weeks, extras


def _wanted_shape(data: TermPlanData) -> tuple:
    weeks = tuple(
        (w.n, w.start, w.end, tuple((i.kind, i.periods, i.lesson, i.unit, i.scope) for i in w.items))
        for w in data.weeks
    )
    extras = [(code, 0) for code in data.enrichment_lessons]
    extras += [(code, n) for code, numbers in data.enrichment_examples.items() for n in numbers]
    return weeks, tuple(sorted(extras))


def sync_term_plan(
    data: TermPlanData, course: Course, lessons: dict[str, Lesson], sources: dict, changed: Counter
) -> TermPlan:
    """الخطة الفصلية: الحقول تُحدَّث في مكانها، والأسابيع والإثرائي تُستبدل كاملة إن اختلفت فقط."""
    window = data.class_during_exams
    wanted = {
        "source": _source(sources, data.source),
        "sessions_per_week": data.sessions_per_week,
        "class_during_exams_start": window.start if window else None,
        "class_during_exams_end": window.end if window else None,
        "lost_days": [d.isoformat() for d in data.lost_days],
        "notes": ([window.note] if window and window.note else []) + list(data.notes),
    }
    plan = TermPlan.objects.filter(course=course).first()
    if plan is None:
        plan = TermPlan.objects.create(course=course, **wanted)
        changed["term_plan"] += 1
    elif _update(plan, wanted):
        changed["term_plan"] += 1
    if _plan_shape(plan) == _wanted_shape(data):
        return plan
    plan.weeks.all().delete()
    plan.enrichments.all().delete()
    for w in data.weeks:
        week = PlanWeek.objects.create(plan=plan, number=w.n, start=w.start, end=w.end)
        PlanEntry.objects.bulk_create(
            PlanEntry(
                week=week,
                order=order,
                kind=item.kind,
                periods=item.periods,
                lesson=lessons[item.lesson] if item.lesson else None,
                unit=item.unit,
                scope=item.scope or "",
            )
            for order, item in enumerate(w.items, start=1)
        )
    rows = [PlanEnrichment(plan=plan, lesson=lessons[code]) for code in data.enrichment_lessons]
    rows += [
        PlanEnrichment(plan=plan, lesson=lessons[code], example=n)
        for code, numbers in data.enrichment_examples.items()
        for n in numbers
    ]
    PlanEnrichment.objects.bulk_create(rows)
    changed["plan_weeks"] += len(data.weeks)
    return plan


def sync_calendar(data: CalendarData, changed: Counter) -> AcademicCalendar:
    """تقويم سنة: الحقول والفصول تُحدَّث في مكانها، وإغلاقات الفصل تُستبدل إن اختلفت فقط."""
    wanted = {
        "weekdays": list(data.weekdays),
        "grades": list(data.grades),
        "verified_primary": data.verified_primary,
        "source_note": data.source,
        "notes": list(data.unknown),
    }
    calendar = AcademicCalendar.objects.filter(year=data.year).first()
    if calendar is None:
        calendar = AcademicCalendar.objects.create(year=data.year, **wanted)
        changed["calendars"] += 1
    elif _update(calendar, wanted):
        changed["calendars"] += 1
    for t in data.terms:
        term, created = CalendarTerm.objects.get_or_create(
            calendar=calendar, semester=t.semester, defaults={"start": t.start, "end": t.end}
        )
        if created or _update(term, {"start": t.start, "end": t.end}):
            changed["calendar_terms"] += 1
        current = sorted((e.kind, e.start, e.end, e.label, e.grades) for e in term.events.all())
        wanted_events = sorted((c.kind, c.start, c.end, c.label, list(c.grades)) for c in t.closures)
        if current != wanted_events:
            term.events.all().delete()
            CalendarEvent.objects.bulk_create(
                CalendarEvent(term=term, kind=k, start=s, end=e, label=label, grades=g)
                for k, s, e, label, g in wanted_events
            )
            changed["calendar_events"] += len(wanted_events)
    return calendar
