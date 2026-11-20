"""تحميل معرفة المنهج من الملفات المنسقة إلى قاعدة البيانات. idempotent: التشغيل الثاني لا يغيّر شيئًا.

يتحقق من كل شيء بالمخططات قبل أن يكتب، ثم يكتب في معاملة واحدة. صفوف الأبناء تُستبدل كاملةً فقط إن اختلف محتواها.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from apps.curriculum import services as curriculum
from apps.curriculum.courses import GRADE12_SLUG
from apps.curriculum.models import Course, Lesson
from apps.curriculum.services import OwnerError

from .domain.contract import (
    SCHEMA_VERSION,
    CourseKnowledge,
    CourseMeta,
    read_calendars,
    read_source,
    source_slugs,
)
from .domain.schemas import LessonData, PedagogyData, UnitData, lesson_sort_key
from .models import (
    ExerciseGroup,
    ExerciseTemplate,
    KnowledgeRelease,
    LessonItem,
    LessonObjective,
    LessonProfile,
    PedagogyNote,
    Practice,
    Standard,
    Term,
    UnitProfile,
    UnitProject,
    WorkedExample,
)


@dataclass
class LoadReport:
    changed: Counter = field(default_factory=Counter)
    content_hash: str = ""

    @property
    def total(self) -> int:
        return sum(self.changed.values())


def _canonical(rows: list[Any]) -> list[str]:
    return sorted(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) for row in rows)


def _sync_children(
    report: LoadReport, name: str, manager: Any, rows: list[dict[str, Any]], model: Any, **parent
) -> None:
    """يستبدل الصفوف كاملةً فقط إن اختلفت عن المطلوب (مقارنة بالحقول المعروفة)."""
    fields = list(rows[0]) if rows else []
    current = list(manager.values(*fields)) if fields else list(manager.all())
    if _canonical(current) == _canonical(rows):  # مقارنة لا تتأثر بترتيب التجميع في قاعدة البيانات
        return
    manager.all().delete()
    model.objects.bulk_create([model(**parent, **row) for row in rows])
    report.changed[name] += 1


def _item_rows(data: LessonData) -> list[dict[str, Any]]:
    seen: Counter = Counter()
    rows = []
    for item in data.items:
        seen[item.kind] += 1
        rows.append({"kind": item.kind, "order": seen[item.kind], "label": item.label, "text": item.text})
    return sorted(rows, key=lambda r: (r["kind"], r["order"]))


def _load_lesson(data: LessonData, lessons: dict[str, Lesson], report: LoadReport) -> None:
    lesson = lessons[data.lesson]
    wanted = {
        "source": data.source,
        "status": data.status,
        "title_en": data.title_en,
        "objective": data.objective,
        "rationale": data.rationale,
        "motivation": data.motivation,
        "self_assessment": data.self_assessment,
        "task_basic": data.task_basic,
        "task_advanced": data.task_advanced,
        "quiz_depths": data.quiz_depths,
        "exercises_total": data.exercises_total,
        "vocab_new": data.vocab_new,
        "vocab_review": data.vocab_review,
    }
    profile, created = LessonProfile.objects.get_or_create(lesson=lesson, defaults=wanted)
    if created:
        report.changed["profiles"] += 1
    elif any(getattr(profile, key) != value for key, value in wanted.items()):
        for key, value in wanted.items():
            setattr(profile, key, value)
        profile.save()
        report.changed["profiles"] += 1

    codes = sorted(data.standards)
    if sorted(profile.standards.values_list("code", flat=True)) != codes:
        profile.standards.set([Standard.objects.get_or_create(code=code)[0] for code in codes])
        report.changed["standards"] += 1

    practices = sorted(data.practices)
    if sorted(profile.practices.values_list("code", flat=True)) != practices:
        profile.practices.set([Practice.objects.get_or_create(code=code)[0] for code in practices])
        report.changed["practices"] += 1

    parent = {"profile": profile}
    objectives = [
        {"order": n, "bloom": o.bloom, "text": o.text} for n, o in enumerate(data.objectives, start=1)
    ]
    _sync_children(report, "objectives", profile.objectives, objectives, LessonObjective, **parent)
    groups = [
        {"order": n, "example": g.example, "dok": g.dok, "exercises": g.exercises, "kind": g.kind}
        for n, g in enumerate(data.exercise_groups, start=1)
    ]
    _sync_children(report, "exercise_groups", profile.exercise_groups, groups, ExerciseGroup, **parent)
    _sync_children(
        report,
        "terms",
        profile.terms,
        sorted(({"ar": t.ar, "en": t.en} for t in data.terms), key=lambda r: r["ar"]),
        Term,
        **parent,
    )
    _sync_children(report, "items", profile.items, _item_rows(data), LessonItem, **parent)
    examples = [
        {
            "number": e.number,
            "page": e.page,
            "skill": e.skill,
            "representation": e.representation,
            "representations": e.representations,
            "methods": e.methods,
        }
        for e in sorted(data.examples, key=lambda e: e.number)
    ]
    _sync_children(report, "examples", profile.examples, examples, WorkedExample, **parent)
    templates = [{"order": order, **t.model_dump()} for order, t in enumerate(data.templates, start=1)]
    _sync_children(report, "templates", profile.templates, templates, ExerciseTemplate, **parent)


def _load_unit(data: UnitData, course: Course, report: LoadReport) -> None:
    wanted = {
        "title": data.title,
        "big_idea": data.big_idea,
        "approach": data.approach,
        "context": data.context,
    }
    unit, created = UnitProfile.objects.get_or_create(course=course, unit=data.unit, defaults=wanted)
    if created or any(getattr(unit, key) != value for key, value in wanted.items()):
        for key, value in wanted.items():
            setattr(unit, key, value)
        unit.save()
        report.changed["units"] += 1
    if data.project is None:
        return
    project = data.project.model_dump()
    _, made = UnitProject.objects.update_or_create(unit=unit, defaults=project)
    # update_or_create لا يخبر بتغيّر؛ نقارن قبل الكتابة عبر المحتوى المخزن
    if made:
        report.changed["projects"] += 1


def _load_pedagogy(data: PedagogyData, course: Course, report: LoadReport) -> None:
    wanted = {"title": data.title, "text": data.text, "order": data.order}
    note, created = PedagogyNote.objects.get_or_create(course=course, slug=data.slug, defaults=wanted)
    if created or any(getattr(note, key) != value for key, value in wanted.items()):
        for key, value in wanted.items():
            setattr(note, key, value)
        note.save()
        report.changed["pedagogy"] += 1


def _sync_course(meta: CourseMeta, report: LoadReport) -> Course:
    """ينشئ المقرر أو يحدّث بياناته. `is_current` ليس من العقد: المقرر الافتراضي قرار تشغيل لا معرفة."""
    wanted = meta.model_dump(exclude={"slug"})
    course, created = Course.objects.get_or_create(slug=meta.slug, defaults=wanted)
    if created:
        report.changed["courses"] += 1
    elif any(getattr(course, key) != value for key, value in wanted.items()):
        for key, value in wanted.items():
            setattr(course, key, value)
        course.save()
        report.changed["courses"] += 1
    return course


def _sync_lessons(contract: CourseKnowledge, course: Course, report: LoadReport) -> dict[str, Lesson]:
    existing = {lesson.code: lesson for lesson in Lesson.objects.filter(course=course)}
    for ref in contract.lessons:
        wanted = {
            "title": ref.title,
            "unit": ref.unit,
            "number": lesson_sort_key(ref.code)[1],
            "examinable": ref.examinable,
        }
        lesson = existing.get(ref.code)
        if lesson is None:
            existing[ref.code] = Lesson.objects.create(course=course, code=ref.code, **wanted)
            report.changed["lessons"] += 1
        elif any(getattr(lesson, key) != value for key, value in wanted.items()):
            for key, value in wanted.items():
                setattr(lesson, key, value)
            lesson.save()
            report.changed["lessons"] += 1
    return existing


BlueprintOwnerError = OwnerError  # اسم قديم: جدول مواصفات يملكه مقرر آخر


def latest_release(course: Course) -> KnowledgeRelease | None:
    return course.knowledge_releases.first()


@transaction.atomic
def load_contract(contract: CourseKnowledge) -> LoadReport:
    """المحمِّل الواحد: عقد معرفة لمقرر → الجداول. idempotent، ويسجّل إصدارًا حين تتغير تجزئة المحتوى."""
    report = LoadReport(content_hash=contract.content_hash())
    course = _sync_course(contract.course, report)
    lessons = _sync_lessons(contract, course, report)
    for data in contract.profiles:
        _load_lesson(data, lessons, report)
    for unit in contract.units:
        _load_unit(unit, course, report)
    for note in contract.pedagogy:
        _load_pedagogy(note, course, report)
    sources = curriculum.sync_sources(course, contract.sources, report.changed)
    for blueprint in contract.blueprints:
        curriculum.sync_blueprint(blueprint, course, lessons, sources, report.changed)
    if contract.term_plan is not None:
        curriculum.sync_term_plan(contract.term_plan, course, lessons, sources, report.changed)
    for exam in contract.past_exams:
        curriculum.sync_past_exam(exam, course, lessons, sources, report.changed)
    for cover in contract.coverage:
        curriculum.sync_coverage(cover, lessons, sources, report.changed)
    previous = latest_release(course)
    if previous is None or previous.content_hash != report.content_hash:
        KnowledgeRelease.objects.create(
            course=course,
            schema_version=SCHEMA_VERSION,
            content_hash=report.content_hash,
            report=dict(report.changed),
        )
        report.changed["releases"] += 1
    return report


def load_course(slug: str) -> LoadReport:
    return load_contract(read_source(slug))


@transaction.atomic
def load_calendars() -> Counter:
    """تقاويم السنوات الأكاديمية (مشتركة بين المقررات) → الجداول. idempotent."""
    changed: Counter = Counter()
    for calendar in read_calendars():
        curriculum.sync_calendar(calendar, changed)
    return changed


def load_all() -> dict[str, LoadReport]:
    """التقاويم ثم كل المقررات ذات المصدر؛ التقرير للمقررات (التقاويم يطبع تقريرها `load_course --all`)."""
    load_calendars()
    return {slug: load_course(slug) for slug in source_slugs()}


def load_knowledge(course_slug: str = GRADE12_SLUG) -> LoadReport:
    """اسم قديم للمحمِّل: يحمّل مقررًا واحدًا (الافتراضي الثاني عشر)."""
    return load_course(course_slug)
