"""المدقّقات: كل مدقّق يقارن حقلين من مصدرين مستقلين ويعيد True/False/None (None = لا بيانات للمقارنة فلا يُحسب نجاحًا).

1) مجموع التمارين: أقصى رقم تمرين مدّعى (من جدول التحليل أو الدمج) مقابل سلسلة OCR مستقلة عنه (أرقام بداية الأسطر
   «12.» أو «12)» المتصلة من 1)، فلا يقبل تقديرًا واحدًا بلا شاهد. سلسلة OCR تفوّت آخر رقم عادة، فيُقبل فرق واحد؛ أو تطابق أقصى
   «دليل المهام» (نص مستقل عن صفوف الجدول).
2) أسئلة اختبار الدرس: عدد صفوف جدول التحليل في صفحة الاختبار مقابل أعماقها: أرقام متصلة من 1، لكل سؤال عمق 1..3،
   ورموز المعايير في الصفوف هي رموز الصفحة نفسها.
"""

from __future__ import annotations

import re
from typing import Any

from .config import Book
from .text import chain_max, norm

MAX_QUIZ_QUESTIONS = 12


def exercise_numbers(raw_text: str, ceiling: int = 60) -> set[int]:
    """أرقام التمارين من بدايات الأسطر («12.» أو «12)») في نص صفحة."""
    return {
        int(x)
        for x in re.findall(r"^\s*([0-9]{1,2})\s*[.)]", norm(raw_text), re.MULTILINE)
        if 1 <= int(x) <= ceiling
    }


def task_guide_max(guide: dict[str, Any] | None) -> int:
    """أكبر رقم في مساري «دليل المهام» (أساسي ومتقدم)؛ 0 إن لم يوجد."""
    return max((int(x) for v in (guide or {}).values() for x in re.findall(r"\d+", str(v))), default=0)


def exercise_total(
    claimed_max: int, ocr_numbers: set[int], jump: int, ceiling: int, guide_max: int = 0
) -> bool | None:
    if not claimed_max:
        return None
    chain = min(chain_max(ocr_numbers, jump), ceiling)
    return 0 <= claimed_max - chain <= 1 or claimed_max == guide_max


def quiz_row_pattern(standard_pattern: str) -> re.Pattern[str]:
    std = f"(?:{standard_pattern})"
    return re.compile(
        rf"(?P<codes>{std}(?:\s*[,،]\s*{std})*)"
        # بين الرمز والعمق قد يقحم OCR أسطر نص سؤال (لا يبدأ سطرها برقم فلا تبتلع رمزًا تاليًا)
        r"(?:\s*\n[^\d\n][^\n]*){0,3}\s+(?P<depth>[1-3])\s+(?P<q>\d{1,2})(?!\d)",
        re.IGNORECASE,
    )


def page_codes(book: Book, raw_text: str) -> list[str]:
    return sorted(
        {
            re.sub(r"\s+", "", c).upper()
            for c in re.findall(f"(?:{book['standards']['pattern']})", norm(raw_text), re.IGNORECASE)
        }
    )


def quiz_rows(book: Book, raw_text: str) -> list[dict[str, Any]]:
    """صفوف الجدول: المعيار ثم العمق المعرفي ثم رقم السؤال. المكرَّر يبقى أول صفّ له، وما رقمه خارج 1..MAX ضجيج OCR."""
    pat = quiz_row_pattern(book["standards"]["pattern"])
    code = re.compile(f"(?:{book['standards']['pattern']})", re.IGNORECASE)
    seen: dict[int, dict[str, Any]] = {}
    for m in pat.finditer(norm(raw_text)):
        q = int(m["q"])
        if not 1 <= q <= MAX_QUIZ_QUESTIONS or q in seen:
            continue
        codes = sorted({re.sub(r"\s+", "", c).upper() for c in code.findall(m["codes"])})
        seen[q] = {"q": q, "depth": int(m["depth"]), "standards": codes}
    return [seen[q] for q in sorted(seen)]


def quiz_consistent(rows: list[dict[str, Any]], codes: list[str]) -> bool | None:
    if not rows:
        return None
    return (
        [r["q"] for r in rows] == list(range(1, len(rows) + 1))
        and all(1 <= r["depth"] <= 3 for r in rows)
        and {c for r in rows for c in r["standards"]} == set(codes)
    )


def quiz_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "questions": len(rows),
        "depth": [r["depth"] for r in rows],
        "standards_by_question": {str(r["q"]): r["standards"] for r in rows},
    }


def run(
    book: Book, layout: dict[str, Any], claimed_exercise_max: dict[str, int] | None = None
) -> dict[str, Any]:
    """مدقّقات كل الدروس. claimed_exercise_max: أقصى تمرين مدّعى لكل درس (من جدول التحليل)، وبدونه يبقى المدقّق None."""
    cfg = book.get("exercises", {})
    ceiling, jump = cfg.get("max", 60), cfg.get("jump", 5)
    out: dict[str, Any] = {"book": book.id, "lessons": {}}
    for r in layout["lessons"]:
        if not r["pages_pdf"]:
            continue
        a, z = r["pages_pdf"]
        std_page = r.get("quiz") if book["layout"].get("standard_on", "opener") == "quiz" else r["opener"]
        nums: set[int] = set()
        for n in range(a, z + 1):
            nums |= exercise_numbers(book.page_text(n), ceiling)
        total = exercise_total((claimed_exercise_max or {}).get(r["id"], 0), nums, jump, ceiling)
        quiz = None
        if r.get("quiz"):
            text = book.page_text(r["quiz"])
            rows = quiz_rows(book, text)
            quiz = {
                "summary": quiz_summary(rows),
                "consistent": quiz_consistent(rows, page_codes(book, text)),
            }
        out["lessons"][r["id"]] = {
            "exercise_total_matches_independent_ocr": total,
            "ocr_exercise_chain": min(chain_max(nums, jump), ceiling),
            "quiz": quiz,
            "standard_found": bool(
                re.search(book["standards"]["pattern"], norm(book.page_text(std_page)), re.IGNORECASE)
            )
            if std_page
            else False,
        }
    return out


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    ls = result["lessons"]
    failed = [
        k
        for k, v in ls.items()
        if v["exercise_total_matches_independent_ocr"] is False
        or (v["quiz"] and v["quiz"]["consistent"] is False)
    ]
    return {
        "lessons": len(ls),
        "exercise_total_checked": sum(
            v["exercise_total_matches_independent_ocr"] is not None for v in ls.values()
        ),
        "quiz_checked": sum(bool(v["quiz"]) for v in ls.values()),
        "failed": failed,
    }
