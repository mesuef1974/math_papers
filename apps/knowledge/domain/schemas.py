"""مخططات ملفات المعرفة المنسقة. أي ملف لا يطابقها يُرفض قبل أن يلمس قاعدة البيانات.

الحارس: النصوص بصياغتنا، فلا يُقبل نص طويل جدًا (علامة نسخ) ولا إشارة إلى الكتاب الخام أو صفحاته.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

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
STANDARD_CODE = re.compile(r"^12A\.\d{1,2}\.\d{1,2}$")


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


class ExampleData(_Strict):
    number: int = Field(ge=1)
    skill: Safe
    representation: Safe = ""
    methods: list[Safe] = Field(default_factory=list)


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


class LessonData(_Strict):
    lesson: str = Field(pattern=r"^\d\.\d$")
    title_en: Safe = ""
    standards: list[str] = Field(default_factory=list)
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
    unit: int = Field(ge=1)
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
