"""تطبيق اقتراحات المعلمين المقبولة على ملف الوحدة المعتمد (`docs/teacher_objective_review_plan.md`، جانب المالك).

دالة نقية على بيانات `prep/unit-<n>.json` الخام: تكتب الشرط والمعيار وحدهما من كل اقتراح مقبول، ولا تمس السلوك
وفعله وعمقه (القرار 2). الاقتراح الذي ساوى نصه المعتمد مُطبَّق من قبل فلا يغيّر شيئًا، والذي تغيّر المعتمد بعد كتابته
(بصمته لا تطابق) يُتخطّى ولا يُكتب فوق نص أحدث منه. إن تغيّر شيء صار سطر الاعتماد بتاريخ اليوم، وإلا بقي الملف كما هو،
فالتشغيل مرتين لا يغيّر شيئًا.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date

from .objective_text import digest

APPROVAL_PREFIX = "اعتُمد من المالك — "


@dataclass(frozen=True)
class AcceptedSuggestion:
    suggestion: int
    lesson: str
    example: int
    condition: str
    criterion: str
    base_digest: str


@dataclass(frozen=True)
class ApplyResult:
    raw: dict
    applied: list[AcceptedSuggestion] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.applied)


def _objective(raw: Mapping, lesson: str, example: int) -> dict | None:
    for entry in raw.get("lessons", ()):
        if entry.get("lesson") == lesson:
            for objective in entry.get("objectives", ()):
                if objective.get("example") == example:
                    return objective
    return None


def apply_accepted(raw: Mapping, accepted: Iterable[AcceptedSuggestion], today: date) -> ApplyResult:
    """نسخة جديدة من بيانات الوحدة بعد تطبيق الاقتراحات بترتيبها (الأقدم قرارًا أولًا)."""
    data = copy.deepcopy(dict(raw))
    applied: list[AcceptedSuggestion] = []
    skipped: list[str] = []
    for item in accepted:
        label = f"الاقتراح {item.suggestion} (الدرس {item.lesson} مثال {item.example})"
        objective = _objective(data, item.lesson, item.example)
        if objective is None:
            skipped.append(f"{label}: لا هدف له في ملف الوحدة")
            continue
        current = (objective["condition"], objective["criterion"])
        if current == (item.condition, item.criterion):
            continue
        if digest((objective["behavior"], *current)) != item.base_digest:
            skipped.append(f"{label}: تغيّر النص المعتمد بعد كتابته")
            continue
        objective["condition"], objective["criterion"] = item.condition, item.criterion
        applied.append(item)
    if applied:
        data["approval"] = f"{APPROVAL_PREFIX}{today.isoformat()}"
    return ApplyResult(raw=data, applied=applied, skipped=skipped)
