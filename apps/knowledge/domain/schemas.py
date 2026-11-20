"""مخططات ملفات المعرفة المنسقة. أي ملف لا يطابقها يُرفض قبل أن يلمس قاعدة البيانات.

الحارس: النصوص بصياغتنا، فلا يُقبل نص طويل جدًا (علامة نسخ) ولا إشارة إلى الكتاب الخام أو صفحاته.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from .exercise_pages import ExercisePages, check_ranges

KINDS = (
    "learning_goal", "guide_step", "prerequisite", "concept_step", "think_question", "struggling",
    "fast_finisher", "follow_up", "study_tip", "caution", "reminder", "guidance", "real_world", "history",
    "note", "exercise_note", "common_error", "technology", "connection", "solution_style", "pearl",
)  # fmt: skip
LEVELS = ("K", "A", "R")
BLOOMS = ("تذكر", "فهم", "تطبيق", "تحليل", "تقويم", "إبداع")
CATEGORIES = ("practice", "standard_test", "exploration", "writing", "extension", "group")

MAX_TEXT = 900
_FORBIDDEN = re.compile(
    r"For Qatar|Savvas|ISBN|MoE Use|\bPDF\b|\bp\d{3}\b|(?:ص|صفحة|صفحات|الصفحة|الصفحتين)\s*\.?\s*\d",
    re.IGNORECASE,
)
# رمز المعيار: صف (1 إلى 12) ثم حرف مسار اختياري ثم مجال ورقم، مثل 10.3.2 و12A.3.4 و7.1.12
STANDARD_CODE = re.compile(r"^(?:[1-9]|1[0-2])[A-Z]?\.\d{1,2}\.\d{1,2}$")
# رمز الدرس «وحدة.درس»، والوحدة حتى خانتين (كتب بعشر وحدات فأكثر)
LESSON_CODE = r"^[1-9]\d?\.[1-9]\d?$"
MAX_UNIT = 30
PRACTICE_CODE = re.compile(r"^MP\.\d$")
BLOOM_OR_UNCLASSIFIED = (*BLOOMS, "unclassified")  # الصنف الأخير: بند لم يُصنَّف فلا يُخمَّن
SOURCES = ("authored", "extracted")  # صياغتنا من الدليل، أو مستخرج آليًا ومطابق للمعيار الذهبي
STATUSES = ("draft", "reviewed")
GROUP_KINDS = ("try", "practice")
RANGE = re.compile(r"^\d{1,2}(?:\s*[-–]\s*\d{1,2})?(?:\s*[,،]\s*\d{1,2}(?:\s*[-–]\s*\d{1,2})?)*$")


def lesson_sort_key(code: str) -> tuple[int, ...]:
    """ترتيب عددي لرمز الدرس: 1.10 بعد 1.9 لا قبل 1.2."""
    return tuple(int(part) for part in code.split("."))


def safe_text(value: str) -> str:
    if len(value) > MAX_TEXT:
        raise ValueError(f"نص أطول من {MAX_TEXT} حرفًا، يبدو منسوخًا")
    if _FORBIDDEN.search(value):
        raise ValueError("نص يشير إلى الكتاب الخام أو صفحاته")
    return value


Safe = Annotated[str, AfterValidator(safe_text)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TermData(_Strict):
    ar: Safe
    en: Safe = ""


class ItemData(_Strict):
    kind: Literal[*KINDS]  # type: ignore[valid-type]
    text: Safe
    label: Safe = ""


class ObjectiveData(_Strict):
    bloom: Literal[*BLOOM_OR_UNCLASSIFIED]  # type: ignore[valid-type]
    text: Safe = ""  # فارغ للمصادر التي لا يدخل نصها المستودع


class GroupKind(_Strict):
    """نوع صف التمارين: `try` تمرين المثال نفسه (جدول «تحليل التمارين» أو سطر «حاول أن تحل»)، و`practice` تمارين قسم
    «تمارين» المربوطة بالمثال. الافتراضي لا يُكتب عند التسلسل، فالملفات والتجزئات التي سبقت الحقل لا تتغير."""

    kind: Literal[*GROUP_KINDS] = "try"  # type: ignore[valid-type]

    @model_serializer(mode="wrap")
    def _without_default_kind(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data = handler(self)
        if data.get("kind") == "try":
            del data["kind"]
        return data


class ExerciseGroupData(GroupKind):
    """صف من تحليل التمارين: مثال وعمق معرفي وأرقام التمارين المرتبطة بهما."""

    example: int = Field(ge=1, le=20)
    dok: int = Field(ge=1, le=4)
    exercises: list[int] = Field(min_length=1)


REPRESENTATIONS = ("جدول", "بياني", "جبري", "سياق")  # تمثيلات المثال المعدودة (فهرس المقرر ومعايير التحضير)
_REPRESENTATION_WORDS = {
    "جدول": ("جدول",),
    "بياني": ("بياني", "رسم"),
    "جبري": ("جبري",),
    "سياق": ("سياق", "تطبيقي"),
}


def representations_in(text: str) -> list[str]:
    """تمثيلات المثال المعدودة من وصفه بصياغتنا («جبري وبياني (الشكل 3.1.4)»): «تطبيقي» سياق، وما لا يقابله تمثيل يُترك."""
    return [r for r in REPRESENTATIONS if any(word in text for word in _REPRESENTATION_WORDS[r])]


class ExampleData(_Strict):
    number: int = Field(ge=1)
    page: int | None = Field(default=None, ge=1, le=999)  # صفحته المطبوعة في كتاب الطالب إن عُرفت
    skill: Safe = ""
    representation: Safe = ""
    representations: list[Literal[*REPRESENTATIONS]] = Field(default_factory=list)  # type: ignore[valid-type]
    methods: list[Safe] = Field(default_factory=list)

    def model_post_init(self, __context: object) -> None:
        if not self.representations and self.representation:
            self.representations = representations_in(self.representation)


class TemplateData(_Strict):
    label: Safe
    directive_template: Safe = ""
    skill: Safe
    representation: Safe = ""
    level: Literal["", *LEVELS] = ""  # type: ignore[valid-type]
    bloom: Literal["", *BLOOMS] = ""  # type: ignore[valid-type]
    inference_note: Safe = ""
    count: int = Field(default=1, ge=1)
    category: Literal[*CATEGORIES] = "practice"  # type: ignore[valid-type]


def _standard(code: str) -> str:
    if not STANDARD_CODE.match(code):
        raise ValueError(f"رمز معيار غير صالح: {code}")
    return code


def _practice(code: str) -> str:
    if not PRACTICE_CODE.match(code):
        raise ValueError(f"رمز ممارسة غير صالح: {code}")
    return code


def _range(value: str) -> str:
    if value and not RANGE.match(value):
        raise ValueError(f"مدى أرقام غير صالح: {value}")
    return value


class LessonData(_Strict):
    lesson: str = Field(pattern=LESSON_CODE)
    source: Literal[*SOURCES] = "authored"  # type: ignore[valid-type]
    status: Literal[*STATUSES] = "reviewed"  # type: ignore[valid-type]
    title_en: Safe = ""
    standards: list[Annotated[str, AfterValidator(_standard)]] = Field(default_factory=list)
    practices: list[Annotated[str, AfterValidator(_practice)]] = Field(default_factory=list)
    objectives: list[ObjectiveData] = Field(default_factory=list)
    exercise_groups: list[ExerciseGroupData] = Field(default_factory=list)
    task_basic: Annotated[str, AfterValidator(_range)] = ""
    task_advanced: Annotated[str, AfterValidator(_range)] = ""
    quiz_depths: list[int] = Field(default_factory=list)
    exercises_total: int | None = Field(default=None, ge=0, le=99)
    vocab_new: int | None = Field(default=None, ge=0)
    vocab_review: int | None = Field(default=None, ge=0)
    exercise_pages: Annotated[list[ExercisePages], AfterValidator(check_ranges)] = Field(default_factory=list)
    objective: Safe = ""
    rationale: Safe = ""
    motivation: Safe = ""
    self_assessment: list[int] = Field(default_factory=list)
    terms: list[TermData] = Field(default_factory=list)
    items: list[ItemData] = Field(default_factory=list)
    examples: list[ExampleData] = Field(default_factory=list)
    templates: list[TemplateData] = Field(default_factory=list)


class ProjectData(_Strict):
    goal: Safe
    context: Safe = ""
    data_used: Safe = ""
    tasks: list[Safe] = Field(default_factory=list)


class UnitData(_Strict):
    unit: int = Field(ge=1, le=MAX_UNIT)
    title: Safe
    big_idea: Safe = ""
    approach: Safe = ""
    context: Safe = ""
    project: ProjectData | None = None


class PedagogyData(_Strict):
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    title: Safe
    text: Safe
    order: int = Field(default=1, ge=1)
