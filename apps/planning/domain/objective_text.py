"""نص هدف المعلم: تنظيف الشرط والمعيار وبصمة النص (`docs/teacher_objective_review_plan.md`).

المعلم يعدّل الشرط والمعيار فقط، والسلوك وفعله وعمقه من ملف الوحدة المعتمد (القرار 2). النص عادي: يُقصّ طرفاه
وتُضمّ مسافاته وأسطره، ويُرفض ما فيه أحرف تحكم أو وسوم، وطوله بحدود نصوص ملف الوحدة (`unit_prep.TEXT`).
البصمة تكشف تغيّر النص المعتمد بعد تعديل المعلم أو بعد مراجعته، فالقِدم مشتق لا مخزَّن.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable

from apps.knowledge.domain.unit_prep import TEXT

MIN_LENGTH, MAX_LENGTH = TEXT["min_length"], TEXT["max_length"]
NOTE_MAX = 240
DIGEST_LENGTH = 16
TAG = re.compile(r"<[^>]*>|[<>]")
SEPARATOR = "\x1f"


class ObjectiveTextError(ValueError):
    """نص هدف مرفوض: طول خارج الحدود أو حرف تحكم أو وسم."""


def _has_control(value: str) -> bool:
    return any(unicodedata.category(ch) == "Cc" for ch in value)


def clean_part(value: str, label: str, *, minimum: int = MIN_LENGTH, maximum: int = MAX_LENGTH) -> str:
    """جزء نصي مقبول بعد التنظيف، أو `ObjectiveTextError` بسببه."""
    text = " ".join(value.replace("\r", " ").replace("\n", " ").replace("\t", " ").split())
    if _has_control(text):
        raise ObjectiveTextError(f"{label}: فيه حرف تحكم")
    if TAG.search(text):
        raise ObjectiveTextError(f"{label}: لا وسوم ولا علامتا < >")
    if not minimum <= len(text) <= maximum:
        raise ObjectiveTextError(f"{label}: الطول بين {minimum} و{maximum} حرفًا")
    return text


def clean_note(value: str | None) -> str:
    """ملاحظة الاقتراح اختيارية: الفارغة تبقى فارغة، وغيرها بقواعد النص نفسها وحد 240 حرفًا."""
    if value is None or not value.strip():
        return ""
    return clean_part(value, "الملاحظة", minimum=1, maximum=NOTE_MAX)


def digest(parts: Iterable[str | None]) -> str:
    """بصمة ثابتة لأجزاء نصية بترتيبها (SHA-256 مقصوصة)."""
    joined = SEPARATOR.join(p or "" for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:DIGEST_LENGTH]


class ObjectiveNotFoundError(LookupError):
    """لا هدف لهذا المثال في الحصة."""


class ObjectiveLockedError(PermissionError):
    """وحدة الحصة غير معتمدة: أهدافها معلَّقة ولا تُعدَّل."""


def shared_digest(objective) -> str:
    """بصمة نص الهدف المعتمد (السلوك والشرط والمعيار)."""
    return digest((objective.behavior, objective.condition, objective.criterion))
