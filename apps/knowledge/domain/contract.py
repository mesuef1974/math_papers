"""العقد القانوني لمعرفة المقرر (رقم النسخة 1): الصيغة الوحيدة التي يقرؤها المحمِّل.

مقرر = بيانات المقرر وقائمة دروسه (رمز وعنوان ووحدة) وملف معرفة لكل درس ووحدات ومبادئ تربوية.
المصدر مجلد لكل مقرر `apps/knowledge/data/courses/<المقرر>/`، ووجود `course.json` فيه هو ما يسجّل المقرر: إضافة كتاب
مجلدٌ جديد بلا تعديل شيفرة. في المجلد:
- `course.json` (إلزامي): بيانات المقرر وقائمة دروسه؛
- `lessons/lesson_*.json` و`units.json` و`pedagogy.json` (اختيارية): معرفة بصياغتنا؛
- `index.json` (اختياري): فهرس مشتق عدديًا من خط الاستخراج (`course_index.py`)، بلا نص دليل، فحقول دروسه النصية فارغة.
الدرس الواحد له مصدر واحد: ملف بصياغتنا أو سجل في الفهرس المشتق، لا كلاهما.
تجزئة المحتوى (`content_hash`) تُحسب من العقد بعد التحقق، فهي واحدة أيًّا كان شكل المصدر.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .course_index import CourseIndex, LessonIndex
from .schemas import (
    LESSON_CODE,
    MAX_UNIT,
    ExampleData,
    ExerciseGroupData,
    LessonData,
    ObjectiveData,
    PedagogyData,
    UnitData,
)

SCHEMA_VERSION = 1
COURSES_DIR = Path(__file__).resolve().parents[1] / "data" / "courses"
MANIFEST = "course.json"
INDEX = "index.json"
LANGUAGES = ("ar", "en")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CourseMeta(_Strict):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=48)
    title: str = Field(min_length=1, max_length=160)
    grade: int = Field(ge=1, le=12)
    track: str = Field(default="", max_length=60)
    semester: int = Field(ge=1, le=3)
    edition: str = Field(default="", max_length=32)
    language: Literal[*LANGUAGES] = "ar"  # type: ignore[valid-type]


class LessonRef(_Strict):
    code: str = Field(pattern=LESSON_CODE)
    title: str = Field(min_length=1, max_length=120)
    unit: int = Field(ge=1, le=MAX_UNIT)
    examinable: bool = True


class CourseKnowledge(_Strict):
    schema_version: Literal[1] = SCHEMA_VERSION
    course: CourseMeta
    lessons: list[LessonRef]
    profiles: list[LessonData] = Field(default_factory=list)
    units: list[UnitData] = Field(default_factory=list)
    pedagogy: list[PedagogyData] = Field(default_factory=list)

    def model_post_init(self, __context: object) -> None:
        codes = [lesson.code for lesson in self.lessons]
        if len(codes) != len(set(codes)):
            raise ValueError("رمز درس مكرر في قائمة الدروس")
        mismatched = sorted(ref.code for ref in self.lessons if int(ref.code.split(".")[0]) != ref.unit)
        if mismatched:
            raise ValueError(f"وحدة الدرس لا تطابق رمزه: {', '.join(mismatched)}")
        profiled = [p.lesson for p in self.profiles]
        if len(profiled) != len(set(profiled)):
            raise ValueError("أكثر من ملف معرفة للدرس الواحد")
        orphans = sorted(set(profiled) - set(codes))
        if orphans:
            raise ValueError(f"ملف معرفة لدرس غير مذكور في قائمة الدروس: {', '.join(orphans)}")
        units = [unit.unit for unit in self.units]
        if len(units) != len(set(units)):
            raise ValueError("رقم وحدة مكرر")
        slugs = [note.slug for note in self.pedagogy]
        if len(slugs) != len(set(slugs)):
            raise ValueError("معرّف مبدأ تربوي مكرر")

    def content_hash(self) -> str:
        """sha256 للمحتوى المعيَّر: لا يتأثر بترتيب المفاتيح ولا بأسطر الملف ولا بمصدره."""
        canonical = json.dumps(self.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def profile_from_index(lesson: LessonIndex) -> LessonData:
    """سجل فهرس مشتق → ملف معرفة الدرس. لا نص: الأهداف بلوم فقط وحقول النص فارغة."""
    return LessonData(
        lesson=lesson.lesson,
        source="extracted",
        status="reviewed",  # الفهرس لا يُودَع قبل مطابقته للمعيار الذهبي
        standards=lesson.standards,
        practices=lesson.practices,
        objectives=[ObjectiveData(bloom=b) for b in lesson.objectives_bloom],
        examples=[ExampleData(number=e.n, representations=list(e.representations)) for e in lesson.examples],
        exercise_groups=[
            ExerciseGroupData(example=a.example, dok=a.dok, exercises=list(a.exercises))
            for a in lesson.analysis
        ],
        task_basic=lesson.task_guide.basic if lesson.task_guide else "",
        task_advanced=lesson.task_guide.advanced if lesson.task_guide else "",
        quiz_depths=list(lesson.quiz_depths),
        exercises_total=lesson.exercises_total,
        vocab_new=lesson.vocabulary.new,
        vocab_review=lesson.vocabulary.review,
    )


def read_index(directory: Path) -> CourseIndex | None:
    path = directory / INDEX
    return CourseIndex(**_read(path)) if path.is_file() else None


def read_course_dir(directory: Path) -> CourseKnowledge:
    manifest = _read(directory / MANIFEST)
    profiles = [LessonData(**_read(p)) for p in sorted((directory / "lessons").glob("lesson_*.json"))]
    index = read_index(directory)
    if index is not None:
        profiles += [profile_from_index(lesson) for lesson in index.lessons]
    units = directory / "units.json"
    pedagogy = directory / "pedagogy.json"
    knowledge = CourseKnowledge(
        schema_version=manifest["schema_version"],
        course=manifest["course"],
        lessons=manifest["lessons"],
        profiles=profiles,
        units=[UnitData(**u) for u in _read(units)] if units.is_file() else [],
        pedagogy=[PedagogyData(**n) for n in _read(pedagogy)] if pedagogy.is_file() else [],
    )
    if knowledge.course.slug != directory.name:
        raise ValueError(f"اسم المجلد {directory.name} لا يطابق معرّف المقرر {knowledge.course.slug}")
    return knowledge


def source_slugs(root: Path | None = None) -> list[str]:
    """المقررات ذات المصدر: كل مجلد فيه `course.json`، بترتيب ثابت."""
    root = root or COURSES_DIR
    return sorted(p.parent.name for p in root.glob(f"*/{MANIFEST}"))


def course_dir(slug: str, root: Path | None = None) -> Path:
    root = root or COURSES_DIR
    if slug not in source_slugs(root):
        raise KeyError(f"لا مصدر معرفة للمقرر {slug}؛ المتاح: {', '.join(source_slugs(root))}")
    return root / slug


def read_source(slug: str, root: Path | None = None) -> CourseKnowledge:
    return read_course_dir(course_dir(slug, root))


def _signature(directory: Path) -> tuple:
    files = sorted(directory.rglob("*.json"))
    return tuple((str(f), f.stat().st_size, f.stat().st_mtime_ns) for f in files)


@lru_cache(maxsize=64)
def _hash_for(directory: str, signature: tuple) -> str:
    return read_course_dir(Path(directory)).content_hash()


def source_hash(slug: str, root: Path | None = None) -> str:
    """تجزئة مصدر المقرر الحالية على القرص. يُخزَّن حسابها بتوقيع الملفات (المسار والحجم والتعديل)."""
    directory = course_dir(slug, root)
    return _hash_for(str(directory), _signature(directory))


@lru_cache(maxsize=64)
def _index_for(directory: str, signature: tuple) -> CourseIndex | None:
    return read_index(Path(directory))


def source_index(slug: str, root: Path | None = None) -> CourseIndex | None:
    """الفهرس المشتق لمقرر كما في ملفه (None لمقرر بلا فهرس مشتق)؛ يُعاد التحقق منه حين يتغير الملف فقط."""
    directory = course_dir(slug, root)
    return _index_for(str(directory), _signature(directory))
