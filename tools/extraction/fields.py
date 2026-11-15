"""غلاف الحقل: كل قيمة مستخرجة تحمل مصدرها وحالتها، فلا يُخلط المستخرج بالمشتق ولا يُخفى النقص.

المصدر: guide (قرئ من الدليل)، derived (اشتُق بقاعدة)، library (تؤلفه المكتبة التربوية)، teacher (يدخله المعلم).
الحالة: ok (موثوق)، review (يلزمه نظر بشري)، missing (غير موجود أو لم يُستخرج).
"""

from __future__ import annotations

from typing import Any

SOURCES = ("guide", "derived", "library", "teacher")
STATUSES = ("ok", "review", "missing")
_RANK = {s: i for i, s in enumerate(STATUSES)}


def field(value: Any, source: str, status: str, **extra: Any) -> dict[str, Any]:
    if source not in SOURCES:
        raise ValueError(f"مصدر غير معروف: {source!r}")
    if status not in STATUSES:
        raise ValueError(f"حالة غير معروفة: {status!r}")
    return {"value": value, "source": source, "status": status, **extra}


def worst(statuses: list[str]) -> str:
    """أسوأ حالة في المجموعة (missing ثم review ثم ok)؛ فارغة = missing."""
    return max(statuses, key=_RANK.__getitem__, default="missing")
