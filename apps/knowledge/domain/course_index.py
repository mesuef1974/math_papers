"""فهرس المقرر المشتق (لأي كتاب مستخرَج آليًا): أرقام ورموز وفئات مغلقة فقط، بلا نص من دليل المعلم.

المصدر مخرجات خط الاستخراج الخارجية (`tools/extraction`، خارج المستودع). كل حقل هنا إما رقم أو رمز معيار أو قيمة من قائمة مغلقة
(مستوى بلوم، تمثيل)، أو مدى أرقام نصه أرقام وفواصل فقط. نص الهدف وعنوان المثال ومهارته والمصطلحات لا تدخل الفهرس إطلاقًا:
المخطط صارم (`extra="forbid"`) ولا يملك أي حقل نصي حر، فيستحيل أن يمرّ نص دليل عبره.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .schemas import BLOOMS, LESSON_CODE, MAX_UNIT, PRACTICE_CODE, REPRESENTATIONS, GroupKind, lesson_sort_key

BLOOM_VALUES = (*BLOOMS, "unclassified")
_RANGE = r"^\d{1,2}(?:\s*[-–]\s*\d{1,2})?(?:\s*[,،]\s*\d{1,2}(?:\s*[-–]\s*\d{1,2})?)*$"
_RANGE_RE = re.compile(_RANGE)
# اسم التمثيل في المستخرج «سياق حياتي» والفهرس يوحّده إلى «سياق» كما في المعيار الذهبي.
_REPRESENTATION_ALIASES = {"سياق حياتي": "سياق"}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExampleIndex(_Strict):
    n: int = Field(ge=1, le=20)
    page: int | None = Field(
        default=None, ge=1, le=999
    )  # صفحة المثال المطبوعة في كتاب الطالب؛ None إن لم تُعرف
    representations: list[Literal[*REPRESENTATIONS]] = Field(default_factory=list)  # type: ignore[valid-type]


class AnalysisRow(GroupKind):
    """صف من جدول «تحليل التمارين»: مثال وعمق معرفي وأرقام التمارين المرتبطة بهما (ونوعه `kind`، `schemas.GroupKind`)."""

    example: int = Field(ge=1, le=20)
    dok: int = Field(ge=1, le=4)
    exercises: list[int] = Field(min_length=1)


class TaskGuide(_Strict):
    basic: str = Field(pattern=_RANGE)
    advanced: str = Field(pattern=_RANGE)


class VocabularyCount(_Strict):
    new: int = Field(ge=0)
    review: int = Field(ge=0)


class LessonIndex(_Strict):
    lesson: str = Field(pattern=LESSON_CODE)
    unit: int = Field(ge=1, le=MAX_UNIT)
    standards: list[str] = Field(default_factory=list)
    practices: list[str] = Field(default_factory=list)
    objectives_bloom: list[Literal[*BLOOM_VALUES]] = Field(default_factory=list)  # type: ignore[valid-type]
    examples: list[ExampleIndex] = Field(default_factory=list)
    analysis: list[AnalysisRow] = Field(default_factory=list)
    exercises_total: int = Field(ge=0, le=99)
    task_guide: TaskGuide | None = None
    quiz_depths: list[int] = Field(default_factory=list)
    vocabulary: VocabularyCount


class CourseIndex(_Strict):
    schema_version: Literal[1] = 1
    lessons: list[LessonIndex]

    def model_post_init(self, __context: object) -> None:
        codes = [lesson.lesson for lesson in self.lessons]
        if len(codes) != len(set(codes)):
            raise ValueError("رمز درس مكرر في الفهرس المشتق")


def standard_pattern(grade: int) -> re.Pattern[str]:
    """معايير صف المقرر وحده (مثل 10.3.2 أو 12A.3.4): رمز صف آخر في مخرج الاستخراج ضجيج قراءة لا يدخل الفهرس."""
    return re.compile(rf"^{grade}[A-Z]?\.\d{{1,2}}\.\d{{1,2}}$")


def _value(field: Any) -> Any:
    """غلاف `{value, source, status}` في مخرجات الاستخراج؛ المفقود يعطي None."""
    return field.get("value") if isinstance(field, dict) else None


def _clean(items: list[str] | None, pattern: re.Pattern[str]) -> list[str]:
    return sorted({s.strip() for s in items or [] if pattern.match(s.strip())})


def _representations(example: dict) -> list[str]:
    raw = _value(example.get("representation")) or []
    names = {_REPRESENTATION_ALIASES.get(r, r) for r in raw}
    return [r for r in REPRESENTATIONS if r in names]


def _analysis(rows: list[dict] | None) -> list[dict]:
    """صف بلا مثال أو بلا عمق (خلية لم تُقرأ) لا يدخل: ناقص لا يُخمَّن."""
    out = []
    for row in rows or []:
        if row.get("example") and row.get("dok") and row.get("exercises"):
            out.append(
                {"example": row["example"], "dok": row["dok"], "exercises": sorted(set(row["exercises"]))}
            )
    return out


def _printed_page(example: dict, printed: Mapping[int, int]) -> int | None:
    """صفحة المثال المطبوعة: صفحة ملف الدليل (`page_pdf`) عبر جدول الصفحات المطبوعة؛ غيابها يعطي None ولا يُخمَّن."""
    page_pdf = _value(example.get("page_pdf"))
    return printed.get(page_pdf) if isinstance(page_pdf, int) else None


def build_lesson_index(lesson: dict, grade: int, printed: Mapping[int, int] | None = None) -> dict:
    """يشتق سجل الفهرس من مخرج درس واحد؛ كل ما ليس رقمًا أو فئة مغلقة يُهمَل.

    `printed` جدول صفحة ملف الدليل → رقم الصفحة المطبوعة (صفحة الدليل تحمل رقم صفحة الطالب المضمَّنة فيها).
    """
    printed = printed or {}
    vocab = _value(lesson.get("vocabulary")) or []
    guide = _value(lesson.get("task_guide")) or {}
    quiz = _value(lesson.get("lesson_quiz")) or {}
    exercises = _value(lesson.get("exercises")) or []
    objectives = _value(lesson.get("objectives")) or []
    return {
        "lesson": lesson["id"],
        "unit": int(lesson["unit"]),
        "standards": _clean(_value(lesson.get("standards")), standard_pattern(grade)),
        "practices": _clean(_value(lesson.get("practices")), PRACTICE_CODE),
        "objectives_bloom": [
            o.get("bloom") if o.get("bloom") in BLOOMS else "unclassified" for o in objectives
        ],
        "examples": [
            {"n": int(e["n"]), "page": _printed_page(e, printed), "representations": _representations(e)}
            for e in sorted(lesson.get("examples") or [], key=lambda e: int(e["n"]))
        ],
        "analysis": _analysis(_value(lesson.get("exercise_analysis"))),
        "exercises_total": max(exercises, default=0),
        "task_guide": (
            {"basic": guide["basic"], "advanced": guide["advanced"]}
            if _RANGE_RE.match(guide.get("basic", "")) and _RANGE_RE.match(guide.get("advanced", ""))
            else None
        ),
        "quiz_depths": [d for d in quiz.get("depth", []) if isinstance(d, int)],
        "vocabulary": {
            "new": sum(v.get("kind") == "new" for v in vocab),
            "review": sum(v.get("kind") == "review" for v in vocab),
        },
    }


def build_index(lessons: list[dict], grade: int, printed: Mapping[int, int] | None = None) -> CourseIndex:
    ordered = sorted(lessons, key=lambda d: lesson_sort_key(d["id"]))
    return CourseIndex(lessons=[LessonIndex(**build_lesson_index(d, grade, printed)) for d in ordered])
