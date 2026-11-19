"""ملف تحضير الوحدة في العقد القانوني: `prep/unit-<n>.json` في مجلد المقرر.

أهداف أمثلة الوحدة بصيغة ABCD بصياغتنا (المتعلّم والسلوك والشرط والمعيار)، هدف لكل مثال غير إثرائي، وحالة الوحدة:
`draft` حتى يكتب المالك سطر اعتماده فتصير `approved` (المعيار T2ج في `apps/planning/domain/prep_checks.py`). لا نص من
الدليل: السلوك يبدأ بفعل من جدول أفعال عمق المثال (`VERBS_BY_DOK`)، والعقد يتحقق منه ومن انتماء الدرس والمثال إلى المقرر
(`CourseKnowledge._check_prep_units`). التصميم: `docs/lesson_prep_plan.md`، «نصوص الأهداف والمراحل والمعايير».
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from .schemas import LESSON_CODE, MAX_UNIT
from .sources import Strict

PREP_STATUSES = ("draft", "approved")
PREP_DIR = "prep"
PREP_FILE = re.compile(r"^unit-(\d{1,2})\.json$")
TEXT = {"min_length": 3, "max_length": 240}


class PrepObjectiveData(Strict):
    lesson: str = Field(pattern=LESSON_CODE)
    example: int = Field(ge=1, le=40)
    behavior: str = Field(**TEXT)
    condition: str = Field(**TEXT)
    criterion: str = Field(**TEXT)

    @property
    def verb(self) -> str:
        """فعل الهدف: الكلمة الأولى في السلوك."""
        return self.behavior.split()[0]


class PrepUnitData(Strict):
    unit: int = Field(ge=1, le=MAX_UNIT)
    status: Literal[*PREP_STATUSES]  # type: ignore[valid-type]
    approval: str = Field(default="", max_length=200)  # سطر اعتماد المالك وتاريخه
    audience: str = Field(min_length=3, max_length=80)
    objectives: list[PrepObjectiveData] = Field(min_length=1)

    def model_post_init(self, __context: object) -> None:
        if self.status == "approved" and not self.approval.strip():
            raise ValueError(f"الوحدة {self.unit} معتمدة بلا سطر اعتماد المالك")
        if self.status == "draft" and self.approval.strip():
            raise ValueError(f"الوحدة {self.unit} مسودة ومعها سطر اعتماد")
        keys = [(o.lesson, o.example) for o in self.objectives]
        repeated = sorted({k for k in keys if keys.count(k) > 1})
        if repeated:
            raise ValueError(f"الوحدة {self.unit}: أكثر من هدف للمثال {repeated}")
        foreign = sorted({o.lesson for o in self.objectives if int(o.lesson.split(".")[0]) != self.unit})
        if foreign:
            raise ValueError(f"الوحدة {self.unit}: أهداف لدروس من وحدة أخرى {', '.join(foreign)}")
