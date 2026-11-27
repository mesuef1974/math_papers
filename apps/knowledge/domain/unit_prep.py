"""نصوص التحضير المؤلَّفة بصياغتنا (القراران 2 و3 في `docs/lesson_prep_plan.md`).

في مجلد المقرر ملفان اختياريان تكتبهما مهارة «مستشار تربوي» مرة لكل وحدة ويعتمدهما المالك وحدةً وحدة:
- `prep/unit-<n>.json`: هدف إجرائي واحد لكل مثال غير إثرائي في دروس الوحدة، بأجزاء ABCD (المتعلم مشترك للوحدة، والسلوك
  يبدأ بفعله، والشرط، والمعيار)، وعمق المثال وفعله. حالته `draft` ثم `approved` بسطر اعتماد المالك.
- `standards.json`: وصف قصير بصياغتنا لكل رمز معيار ووحدته؛ يظهر حين يُعتمد ملف وحدته.
لا نص من دليل المعلم أو الكتاب: المهارة تكتب من رمز المعيار ومهارة المثال وتمثيلاته وعمق تدريباته.
الملفات خارج العقد القانوني والمحمِّل (كمكتبة الاستراتيجيات)؛ تُقرأ من المجلد وتُفحص بهذا المخطط، ومطابقتها للفهرس
(الأمثلة والأعماق) يفحصها `unit_problems` ومعايير التحضير T2 وT2ج.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .contract import COURSES_DIR
from .course_index import LessonIndex
from .schemas import LESSON_CODE, MAX_UNIT

PREP_DIR = "prep"
STANDARDS = "standards.json"
APPROVAL = re.compile(r"^اعتُمد من المالك — \d{4}-\d{2}-\d{2}$")
STANDARD_CODE = r"^\d{1,2}[A-Z]?\.\d{1,2}\.\d{1,2}$"
TEXT = {"min_length": 3, "max_length": 240}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthoredObjective(_Strict):
    example: int = Field(ge=1, le=40)
    dok: int = Field(ge=1, le=4)
    verb: str = Field(min_length=2, max_length=16)
    behavior: str = Field(**TEXT)
    condition: str = Field(**TEXT)
    criterion: str = Field(**TEXT)
    # معايير المثال (من معايير درسه)؛ فارغة لوحدة لم تُربط بعد
    standards: tuple[str, ...] = ()

    def model_post_init(self, __context: object) -> None:
        bad = [code for code in self.standards if not re.match(STANDARD_CODE, code)]
        if bad or list(self.standards) != sorted(set(self.standards)):
            raise ValueError(f"المثال {self.example}: معايير غير صالحة أو مكررة أو غير مرتبة")
        if self.behavior.split()[0] != self.verb:
            raise ValueError(f"المثال {self.example}: السلوك لا يبدأ بفعله «{self.verb}»")


class LessonObjectives(_Strict):
    lesson: str = Field(pattern=LESSON_CODE)
    objectives: list[AuthoredObjective] = Field(min_length=1)

    def model_post_init(self, __context: object) -> None:
        numbers = [o.example for o in self.objectives]
        if numbers != sorted(set(numbers)):
            raise ValueError(f"الدرس {self.lesson}: أمثلة الأهداف مكررة أو غير مرتبة")


class UnitPrep(_Strict):
    schema_version: Literal[1] = 1
    course: str = Field(min_length=1, max_length=48)
    unit: int = Field(ge=1, le=MAX_UNIT)
    status: Literal["draft", "approved"]
    approval: str | None = None
    audience: str = Field(**TEXT)
    lessons: list[LessonObjectives] = Field(min_length=1)

    def model_post_init(self, __context: object) -> None:
        if self.status == "approved" and not APPROVAL.match(self.approval or ""):
            raise ValueError(f"الوحدة {self.unit}: معتمدة بلا سطر اعتماد المالك")
        if self.status == "draft" and self.approval:
            raise ValueError(f"الوحدة {self.unit}: مسودة بسطر اعتماد")
        codes = [lesson.lesson for lesson in self.lessons]
        if len(codes) != len(set(codes)):
            raise ValueError(f"الوحدة {self.unit}: درس مكرر")

    def objectives(self, lesson: str) -> dict[int, AuthoredObjective]:
        return {o.example: o for entry in self.lessons if entry.lesson == lesson for o in entry.objectives}


class StandardText(_Strict):
    unit: int = Field(ge=1, le=MAX_UNIT)
    text: str = Field(**TEXT)


class CourseStandards(_Strict):
    schema_version: Literal[1] = 1
    course: str = Field(min_length=1, max_length=48)
    note: str = ""
    standards: dict[str, StandardText]

    def model_post_init(self, __context: object) -> None:
        bad = [code for code in self.standards if not re.match(STANDARD_CODE, code)]
        if bad:
            raise ValueError(f"رمز معيار غير صالح: {bad}")


def _read(path: Path) -> object | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


@lru_cache(maxsize=64)
def unit_prep(course: str, unit: int, root: Path = COURSES_DIR) -> UnitPrep | None:
    """ملف الوحدة المؤلَّف؛ None إن لم يُكتب بعد."""
    raw = _read(root / course / PREP_DIR / f"unit-{unit}.json")
    if raw is None:
        return None
    data = UnitPrep.model_validate(raw)
    if data.course != course or data.unit != unit:
        raise ValueError(f"ملف الوحدة {unit} للمقرر {course} يعلن {data.course} والوحدة {data.unit}")
    return data


def unit_files(course: str, root: Path = COURSES_DIR) -> list[int]:
    folder = root / course / PREP_DIR
    if not folder.is_dir():
        return []
    return sorted(
        int(m.group(1)) for p in folder.iterdir() if (m := re.fullmatch(r"unit-(\d+)\.json", p.name))
    )


@lru_cache(maxsize=16)
def course_standards(course: str, root: Path = COURSES_DIR) -> CourseStandards | None:
    raw = _read(root / course / STANDARDS)
    if raw is None:
        return None
    data = CourseStandards.model_validate(raw)
    if data.course != course:
        raise ValueError(f"standards.json للمقرر {course} يعلن {data.course}")
    return data


def approved_standards(course: str, root: Path = COURSES_DIR) -> dict[str, str]:
    """أوصاف المعايير التي اعتُمد ملف وحدتها؛ ما سواها لا يظهر (T2ج)."""
    data = course_standards(course, root)
    if data is None:
        return {}
    out = {}
    for code, entry in data.standards.items():
        unit = unit_prep(course, entry.unit, root)
        if unit is not None and unit.status == "approved":
            out[code] = entry.text
    return out


def unit_problems(
    data: UnitPrep,
    lessons: Iterable[LessonIndex],
    enrichment_lessons: Iterable[str],
    enrichment_examples: Mapping[str, Iterable[int]],
    standards: CourseStandards | None,
) -> list[str]:
    """مطابقة ملف الوحدة للفهرس: هدف لكل مثال غير إثرائي في كل درس غير إثرائي، بعمق أعلى صف في تحليله، ووصف لكل معيار."""
    problems: list[str] = []
    skip = set(enrichment_lessons)
    own = [lesson for lesson in lessons if lesson.unit == data.unit and lesson.lesson not in skip]
    written = {entry.lesson for entry in data.lessons}
    expected = {lesson.lesson for lesson in own}
    problems += [f"درس ليس في الوحدة أو إثرائي: {code}" for code in sorted(written - expected)]
    problems += [f"درس بلا أهداف: {code}" for code in sorted(expected - written)]
    for lesson in own:
        objectives = data.objectives(lesson.lesson)
        extra = set(enrichment_examples.get(lesson.lesson, ()))
        examples = [e.n for e in lesson.examples if e.n not in extra]
        if sorted(objectives) != examples:
            problems.append(f"الدرس {lesson.lesson}: أهداف للأمثلة {sorted(objectives)} والأمثلة {examples}")
        depth: dict[int, int] = {}
        for row in lesson.analysis:
            depth[row.example] = max(depth.get(row.example, 0), row.dok)
        for n, objective in objectives.items():
            if objective.dok != max(depth.get(n, 1), 1):
                problems.append(f"الدرس {lesson.lesson} مثال {n}: العمق {objective.dok} لا يطابق الفهرس")
        codes = set(lesson.standards)
        linked = any(o.standards for entry in data.lessons for o in entry.objectives)
        for n, objective in objectives.items():
            if linked and not objective.standards:
                problems.append(f"الدرس {lesson.lesson} مثال {n}: بلا معيار")
            outside = sorted(set(objective.standards) - codes)
            if outside:
                problems.append(f"الدرس {lesson.lesson} مثال {n}: معيار ليس من معايير الدرس {outside}")
        missing = sorted(codes - set(standards.standards if standards else ()))
        problems += [f"الدرس {lesson.lesson}: معيار بلا وصف {code}" for code in missing]
    return problems
