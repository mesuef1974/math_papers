"""مصدر فكرة السؤال في كتاب الطالب: رقم الصفحة المطبوعة ورقم المثال أو التدريب. أرقام فقط، بلا نص من الكتاب.

يُشتق عند التوليد من رقم المثال الذي تصرّح به الصيغة (`variant(..., example=N)`) وصفحته في فهرس المقرر، ويُعرض في المفتاح
بصيغة واحدة على الشاشة والطباعة وWord: «ص 5، مثال 1»، أو «مثال 1» إن لم تُعرف الصفحة. ومع المثال تدريبات الكتاب التي
تتدرّب عليه (من جدول «تحليل التمارين» في الفهرس): «ص 26، مثال 1، تدريب 13، 20، 21». صيغ العاشر والثاني عشر كلها برقم مثال،
والمقرر الذي لم تُحمَّل صفحات أمثلته وتدريباتها بعد مصدره «مثال N» وحده، والصيغة بلا مثال بلا مصدر.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

KIND_NAMES = {"example": "مثال", "practice": "تدريب"}


def book_source(
    number: int | None, page: int | None, kind: str = "example", exercises: list[int] | None = None
) -> dict[str, Any] | None:
    """المفتاح «exercises» يُضاف حين تُعرف تدريبات المثال فقط، فالمصدر بلا تدريبات يبقى كما كان."""
    if number is None:
        return None
    source: dict[str, Any] = {"kind": kind, "number": number, "page": page}
    if exercises:
        source["exercises"] = sorted(set(exercises))
    return source


def book_ref(word: str, number: int, page: int | None) -> str:
    """المصدر الوحيد لنص الإشارة إلى مثال أو تمرين بعينه: «مثال 3 (ص 12)»؛ والصفحة المجهولة لا تُخترع. `word` «مثال»
    أو «المثال» أو «التمرين» حسب موقعه من الجملة. نظيره في الواجهة `utils/bookRef.ts` (قرار المالك 2026-11-27)."""
    return f"{word} {number} (ص {page})" if page else f"{word} {number}"


def number_list(numbers: list[int]) -> str:
    """«9، 11، 16–19، 27»: الأرقام المتتالية ثلاثةً فأكثر مدى واحد."""
    runs: list[list[int]] = []
    for n in sorted(set(numbers)):
        if runs and n == runs[-1][-1] + 1:
            runs[-1].append(n)
        else:
            runs.append([n])
    return "، ".join(f"{run[0]}–{run[-1]}" if len(run) >= 3 else "، ".join(map(str, run)) for run in runs)


def numbers_with_pages(numbers: list[int], pages: Mapping[int, int]) -> str:
    """«14، 15 (ص 9)؛ 30 (ص 10)»: أرقام تمارين الكتاب مجموعة بصفحاتها المطبوعة بترتيب الأرقام؛ التمرين بلا صفحة معروفة رقمه
    وحده في مجموعة بلا صفحة، وبلا أي صفحة معروفة النص `number_list` نفسه."""
    groups: list[tuple[int | None, list[int]]] = []
    for n in sorted(set(numbers)):
        page = pages.get(n)
        if groups and groups[-1][0] == page:
            groups[-1][1].append(n)
        else:
            groups.append((page, [n]))
    return "؛ ".join(
        f"{number_list(nums)} (ص {page})" if page is not None else number_list(nums) for page, nums in groups
    )


def source_cells(source: Mapping[str, Any] | None) -> dict[str, str]:
    """خلايا المصدر في أعمدة المفتاح الثلاثة «الصفحة» و«المثال» و«التدريب» (قرار المالك 2026-11-19)، مشتقة من
    أرقام المصدر وحدها في الخادم وWord، فلا تغيب حين لا يصل نص مشتق مع الجزء. الخانة المجهولة فارغة لا مخترعة.
    مصدر من نوع التدريب (لا مثال له) رقمه في عمود «التدريب»."""
    if not source:
        return {"page": "", "example": "", "exercises": ""}
    page = str(source["page"]) if source.get("page") else ""
    if source["kind"] == "practice":
        return {"page": page, "example": "", "exercises": str(source["number"])}
    return {
        "page": page,
        "example": str(source["number"]),
        "exercises": number_list(source["exercises"]) if source.get("exercises") else "",
    }


def source_label(source: Mapping[str, Any] | None) -> str:
    if not source:
        return ""
    item = f"{KIND_NAMES[source['kind']]} {source['number']}"
    label = f"ص {source['page']}، {item}" if source.get("page") else item
    if source.get("exercises"):
        label += f"، تدريب {number_list(source['exercises'])}"
    return label
