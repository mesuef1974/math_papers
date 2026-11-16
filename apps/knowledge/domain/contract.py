"""العقد القانوني لمعرفة المقرر (رقم النسخة 1): الصيغة الوحيدة التي يقرؤها المحمِّل.

مقرر = بيانات المقرر وقائمة دروسه (رمز وعنوان ووحدة) وملف معرفة لكل درس ووحدات ومبادئ تربوية. المصادر الممكنة:
- مجلد في `apps/knowledge/data/courses/<المقرر>/` (`course.json` و`units.json` و`pedagogy.json` و`lessons/lesson_*.json`)
  وهو للثاني عشر، نصه بصياغتنا؛
- محوِّل من مصدر مشتق عدديًا (فهرس العاشر): لا نص دليل فيه، فحقوله النصية فارغة وبنوده أرقام وفئات مغلقة.
تجزئة المحتوى (`content_hash`) تُحسب من العقد بعد التحقق، فهي واحدة أيًّا كان المصدر.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from apps.curriculum.courses import GRADE10_SLUG, GRADE12_SLUG

from .grade10_index import Grade10Index
from .schemas import (
    ExampleData,
    ExerciseGroupData,
    LessonData,
    ObjectiveData,
    PedagogyData,
    UnitData,
)

SCHEMA_VERSION = 1
COURSES_DIR = Path(__file__).resolve().parents[1] / "data" / "courses"
GRADE10_INDEX_FILE = Path(__file__).resolve().parents[1] / "data" / "grade10_index.json"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CourseMeta(_Strict):
    slug: str = Field(pattern=r"^[a-z0-9-]+$", max_length=48)
    title: str = Field(max_length=160)
    grade: int = Field(ge=1, le=12)
    track: str = ""
    semester: int = Field(ge=1, le=3)
    edition: str = ""


class LessonRef(_Strict):
    code: str = Field(pattern=r"^\d\.\d{1,2}$")
    title: str = Field(max_length=120)
    unit: int = Field(ge=1)
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
        orphans = sorted(p.lesson for p in self.profiles if p.lesson not in set(codes))
        if orphans:
            raise ValueError(f"ملف معرفة لدرس غير مذكور في قائمة الدروس: {', '.join(orphans)}")

    def content_hash(self) -> str:
        """sha256 للمحتوى المعيَّر: لا يتأثر بترتيب المفاتيح ولا بأسطر الملف ولا بمصدره."""
        canonical = json.dumps(self.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_course_dir(directory: Path) -> CourseKnowledge:
    manifest = _read(directory / "course.json")
    return CourseKnowledge(
        schema_version=manifest["schema_version"],
        course=manifest["course"],
        lessons=manifest["lessons"],
        profiles=[LessonData(**_read(p)) for p in sorted((directory / "lessons").glob("lesson_*.json"))],
        units=[UnitData(**u) for u in _read(directory / "units.json")],
        pedagogy=[PedagogyData(**n) for n in _read(directory / "pedagogy.json")],
    )


def grade10_to_contract(index: Grade10Index) -> CourseKnowledge:
    """يحوّل فهرس العاشر المشتق إلى العقد. لا نص: العنوان «الدرس <رمز>» والأهداف بلوم فقط."""
    profiles = []
    for lesson in index.lessons:
        profiles.append(
            LessonData(
                lesson=lesson.lesson,
                source="extracted",
                status="reviewed",  # الفهرس مطابق للمعيار الذهبي (36 من 36) قبل أن يُودَع
                standards=lesson.standards,
                practices=lesson.practices,
                objectives=[ObjectiveData(bloom=b) for b in lesson.objectives_bloom],
                examples=[
                    ExampleData(number=e.n, representations=list(e.representations)) for e in lesson.examples
                ],
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
        )
    return CourseKnowledge(
        course=CourseMeta(
            slug=GRADE10_SLUG,
            title="الرياضيات: العاشر، الفصل الأول",
            grade=10,
            semester=1,
        ),
        lessons=[
            LessonRef(code=lesson.lesson, title=f"الدرس {lesson.lesson}", unit=lesson.unit)
            for lesson in index.lessons
        ],
        profiles=profiles,
    )


def _grade10() -> CourseKnowledge:
    return grade10_to_contract(Grade10Index(**_read(GRADE10_INDEX_FILE)))


def _grade12() -> CourseKnowledge:
    return read_course_dir(COURSES_DIR / GRADE12_SLUG)


# المقرر -> (قارئ المصدر، الملفات التي تحدد تجزئته لتخزين حسابها مؤقتًا)
SOURCES = {
    GRADE12_SLUG: (_grade12, lambda: sorted((COURSES_DIR / GRADE12_SLUG).rglob("*.json"))),
    GRADE10_SLUG: (_grade10, lambda: [GRADE10_INDEX_FILE]),
}


def source_slugs() -> list[str]:
    return list(SOURCES)


def read_source(slug: str) -> CourseKnowledge:
    if slug not in SOURCES:
        raise KeyError(f"لا مصدر معرفة للمقرر {slug}؛ المتاح: {', '.join(SOURCES)}")
    return SOURCES[slug][0]()


@lru_cache(maxsize=16)
def _hash_for(slug: str, signature: tuple) -> str:
    return read_source(slug).content_hash()


def source_hash(slug: str) -> str:
    """تجزئة مصدر المقرر الحالية على القرص. يُخزَّن حسابها بتوقيع الملفات (المسار والحجم والتعديل)."""
    files = SOURCES[slug][1]()
    signature = tuple((str(f), f.stat().st_size, f.stat().st_mtime_ns) for f in files)
    return _hash_for(slug, signature)
