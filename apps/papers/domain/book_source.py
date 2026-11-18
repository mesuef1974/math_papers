"""مصدر فكرة السؤال في كتاب الطالب: رقم الصفحة المطبوعة ورقم المثال أو التدريب. أرقام فقط، بلا نص من الكتاب.

يُشتق عند التوليد من رقم المثال الذي تصرّح به الصيغة (`variant(..., example=N)`) وصفحته في فهرس المقرر، ويُعرض في المفتاح
بصيغة واحدة على الشاشة والطباعة وWord: «ص 5، مثال 1»، أو «مثال 1» إن لم تُعرف الصفحة. الصيغة بلا مثال (كالثاني عشر) بلا مصدر.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

KIND_NAMES = {"example": "مثال", "practice": "تدريب"}


def book_source(number: int | None, page: int | None, kind: str = "example") -> dict[str, Any] | None:
    if number is None:
        return None
    return {"kind": kind, "number": number, "page": page}


def source_label(source: Mapping[str, Any] | None) -> str:
    if not source:
        return ""
    item = f"{KIND_NAMES[source['kind']]} {source['number']}"
    return f"ص {source['page']}، {item}" if source.get("page") else item
