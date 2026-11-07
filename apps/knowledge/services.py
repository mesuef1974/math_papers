"""تحميل معرفة المنهج من الملفات المنسقة إلى قاعدة البيانات. idempotent: التشغيل الثاني لا يغيّر شيئًا.

يتحقق من كل شيء بالمخططات قبل أن يكتب، ثم يكتب في معاملة واحدة. صفوف الأبناء تُستبدل كاملةً فقط إن اختلف محتواها.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.db import transaction

from apps.curriculum.models import Lesson

from .domain.schemas import LessonData, PedagogyData, UnitData
from .models import (
    ExerciseTemplate,
    LessonItem,
    LessonProfile,
    PedagogyNote,
    Standard,
    Term,
    UnitProfile,
    UnitProject,
    WorkedExample,
)

DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass
class LoadReport:
    changed: Counter = field(default_factory=Counter)
    skipped: list[str] = field(default_factory=list)  # دروس في الملفات وليست في منهج المنصة

    @property
    def total(self) -> int:
        return sum(self.changed.values())


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
        "title_en": data.title_en,
        "objective": data.objective,
        "rationale": data.rationale,
        "motivation": data.motivation,
        "self_assessment": data.self_assessment,
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

    parent = {"profile": profile}
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
        {"number": e.number, "skill": e.skill, "representation": e.representation, "methods": e.methods}
        for e in sorted(data.examples, key=lambda e: e.number)
    ]
    _sync_children(report, "examples", profile.examples, examples, WorkedExample, **parent)
    templates = [{"order": order, **t.model_dump()} for order, t in enumerate(data.templates, start=1)]
    _sync_children(report, "templates", profile.templates, templates, ExerciseTemplate, **parent)


def _load_unit(data: UnitData, report: LoadReport) -> None:
    wanted = {
        "title": data.title,
        "big_idea": data.big_idea,
        "approach": data.approach,
        "context": data.context,
    }
    unit, created = UnitProfile.objects.get_or_create(unit=data.unit, defaults=wanted)
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


def _load_pedagogy(data: PedagogyData, report: LoadReport) -> None:
    wanted = {"title": data.title, "text": data.text, "order": data.order}
    note, created = PedagogyNote.objects.get_or_create(slug=data.slug, defaults=wanted)
    if created or any(getattr(note, key) != value for key, value in wanted.items()):
        for key, value in wanted.items():
            setattr(note, key, value)
        note.save()
        report.changed["pedagogy"] += 1


@transaction.atomic
def load_knowledge(data_dir: Path = DATA_DIR) -> LoadReport:
    lessons_data = [LessonData(**_read(p)) for p in sorted((data_dir / "lessons").glob("lesson_*.json"))]
    units_data = [UnitData(**u) for u in _read(data_dir / "units.json")]
    pedagogy_data = [PedagogyData(**n) for n in _read(data_dir / "pedagogy.json")]
    lessons = {lesson.code: lesson for lesson in Lesson.objects.all()}
    report = LoadReport(skipped=sorted(d.lesson for d in lessons_data if d.lesson not in lessons))
    for data in lessons_data:
        if data.lesson in lessons:
            _load_lesson(data, lessons, report)
    for unit in units_data:
        _load_unit(unit, report)
    for note in pedagogy_data:
        _load_pedagogy(note, report)
    return report
