"""دمج OCR والرؤية وجدول التحليل لحقائق كل درس: أرقام التمارين والأمثلة ورموز ممارسات الرياضيات، بثقة لكل رقم وصفحات مراجعة.

الثقة: both (اتفق OCR والرؤية)، ocr أو vision (مصدر واحد)، filled (سُدّ بقيد التسلسل 1..max). الرؤية تختلق قوائم متسلسلة أحيانًا
وOCR يلتقط أرقام جداول معزولة، فالسقف سلسلة متصلة من 1 بفجوة لا تتجاوز `jump`، وكل رقم فوقها يُرفض وتُعلَّم صفحته؛ وجدول تحليل
التمارين (dirs.tables) مصدر OCR موثوق يحدد آخر تمرين. ورقم مثال تنفرد به الرؤية فوق أعلى ما التقطه OCR يلزمه صفحتان.
المصادر: dirs.ocr نص الصفحة، dirs.vision (اختياري) NNNN.json بمفاتيح examples وexercises وpractices، dirs.tables (اختياري).
الإعداد: exercises.max/jump وexamples.max/jump وpractices (marker وnames) وfusion (degenerate وname_tail وexercise_pattern).
"""

from __future__ import annotations

import json
import re
from typing import Any

from .config import Book
from .examples import DEFAULT_PATTERN as EXAMPLE_PATTERN
from .text import chain_max, norm

DEFAULTS: dict[str, Any] = {
    "degenerate": 20,  # قائمة رؤية أطول من هذا في صفحة واحدة تُسقَط وتُعلَّم الصفحة
    "name_tail": 40,  # أقصى ما يزيده سطر العنوان على بداية اسم الممارسة؛ الأطول جملة شرح
    "exercise_pattern": r"^\s*([0-9]{1,2})\s*[.)]",
}
FIELDS = ("exercises", "examples", "practices")
STATUSES = ("both", "ocr", "vision", "filled")
Sets = list[set[Any]]


def settings(book: Book) -> dict[str, Any]:
    ex, eg = book.get("exercises", {}), book.get("examples", {})
    return {
        **DEFAULTS,
        **book.get("fusion", {}),
        "max_exercise": ex.get("max", 60),
        "max_example": eg.get("max", 9),
        "jump": {"exercises": ex.get("jump", 5), "examples": eg.get("jump", 2)},
        "practices": book.get("practices") or {},
    }


def _letters(text: str) -> str:
    """الحروف العربية وحدها بعد التوحيد: يسقط التشكيل والفراغ وبقايا الرمز (M، MP4) الملتصقة بالاسم."""
    return re.sub(r"[^ء-غف-ي]", "", norm(text))


def practice_names(text: str, cfg: dict[str, Any]) -> set[str]:
    """رموز الممارسات من أسمائها بعد عنوان قسمها. الرمز MP.n مطبوع بالرمادي فقد يفوّته OCR والرؤية معًا، والاسم بجانبه يُقرأ."""
    practices = cfg["practices"]
    marker = _letters(practices.get("marker", ""))
    if not marker:
        return set()
    lines = [_letters(line) for line in text.splitlines()]
    start = next((i for i, line in enumerate(lines) if marker in line), None)
    if start is None:
        return set()
    names = [(_letters(name), code) for code, group in practices.get("names", {}).items() for name in group]
    return {
        code
        for line in lines[start + 1 :]
        for name, code in names
        if line.startswith(name) and len(line) <= len(name) + cfg["name_tail"]
    }


def page_sources(book: Book, n: int, cfg: dict[str, Any]) -> dict[str, Any]:
    """أرقام صفحة واحدة بحسب كل مصدر: (OCR، رؤية) لكل حقل."""
    text = norm(book.page_text(n))
    vision = {"examples": [], "exercises": [], "practices": []}
    has_vision = False
    if book.has_dir("vision"):
        path = book.dir("vision") / f"{n:04d}.json"
        if path.exists():
            vision, has_vision = json.loads(path.read_text(encoding="utf-8")), True
    top = cfg["max_exercise"]
    return {
        "exercises": (
            {int(x) for x in re.findall(cfg["exercise_pattern"], text, re.MULTILINE) if 1 <= int(x) <= top},
            {x for x in vision.get("exercises", []) if 1 <= x <= top},
        ),
        "examples": (
            {int(x) for x in re.findall(EXAMPLE_PATTERN, text)},
            {x for x in vision.get("examples", []) if x <= cfg["max_example"]},
        ),
        "practices": (
            set(re.findall(r"MP\.\d", text)) | practice_names(text, cfg),
            set(vision.get("practices", [])),
        ),
        "has_vision": has_vision,
    }


def table_numbers(book: Book, first: int, last: int) -> dict[int, set[int]]:
    """أرقام تمارين جدول التحليل بحسب صفحته، لصفحات الدرس التي لها جدول."""
    if not book.has_dir("tables"):
        return {}
    out: dict[int, set[int]] = {}
    for n in range(first, last + 1):
        path = book.dir("tables") / f"{n:04d}.json"
        if path.exists():
            rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
            out[n] = {x for r in rows for x in r["exercises"]}
    return out


def _reject(rejected: dict[int, list[Any]], review: set[int], n: int, items: set[Any]) -> None:
    if items:
        rejected[n] = sorted(set(rejected.get(n, [])) | items)
        review.add(n)


def fuse(book: Book, first: int, last: int, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """يدمج مصادر صفحات الدرس [first، last]؛ الناتج: review_pages وrejected وحالة كل رقم لكل حقل."""
    cfg = cfg or settings(book)
    pages = {n: page_sources(book, n, cfg) for n in range(first, last + 1)}
    tables = table_numbers(book, first, last)
    t_all: set[int] = set().union(*tables.values()) if tables else set()
    review: set[int] = set()
    out: dict[str, Any] = {"rejected": {}}
    for name in FIELDS:
        cand: dict[int, Sets] = {n: [set(p[name][0]), set(p[name][1])] for n, p in pages.items()}
        if name == "exercises":
            for n, nums in tables.items():
                cand[n][0] |= nums  # الجدول يُعامَل كمصدر OCR موثوق على صفحته
        rejected: dict[int, list[Any]] = {}
        if name == "exercises":
            for n, (ocr, vis) in cand.items():
                if len(vis) > cfg["degenerate"]:
                    _reject(rejected, review, n, vis - ocr)
                    cand[n][1] = vis & ocr
        jump = cfg["jump"].get(name)
        if jump is not None:
            cap = chain_max(set().union(*(o | v for o, v in cand.values())), jump)
            if name == "exercises" and t_all:
                cap = max(t_all)  # الجدول يحدد آخر تمرين فلا رقم فوقه، ولو كانت سلسلة OCR أعلى
            for n, pair in cand.items():
                for i in (0, 1):
                    _reject(rejected, review, n, {x for x in pair[i] if x > cap})
                    pair[i] = {x for x in pair[i] if x <= cap}
        if name == "examples":
            top = max(set().union(*(o for o, _ in cand.values())), default=0)
            for x in {x for _, v in cand.values() for x in v if x > top}:
                pgs = [n for n, (_, v) in cand.items() if x in v]
                if len(pgs) < 2:
                    for n in pgs:
                        _reject(rejected, review, n, {x})
                        cand[n][1] = cand[n][1] - {x}
        status: dict[Any, str] = {}
        where: dict[Any, int] = {}
        for n, (ocr, vis) in cand.items():
            for x in ocr | vis:
                s = "both" if x in ocr and x in vis else ("ocr" if x in ocr else "vision")
                if x not in status or s == "both":
                    status[x], where[x] = s, n
        if jump is not None and status:
            for x in range(1, max(status) + 1):
                if x not in status:
                    status[x] = "filled"
                    near = [where[k] for k in (x - 1, x + 1) if k in where]
                    if near:
                        review |= set(range(min(near), max(near) + 1))
        if name == "exercises" and status and not t_all:
            # الرقم الأخير لا رقم بعده يسنده بقيد التسلسل: تُعلَّم صفحته والتالية
            end = where.get(max(status), last)
            review |= {n for n in (end, end + 1) if first <= n <= last}
        out[name] = status
        out["rejected"][name] = rejected
    out["review_pages"] = review
    return out


def _plain(fused: dict[str, Any]) -> dict[str, Any]:
    """نسخة JSON: المفاتيح نصوص، والقوائم مرتبة."""
    return {
        "review_pages": sorted(fused["review_pages"]),
        "rejected": {f: {str(n): v for n, v in sorted(r.items())} for f, r in fused["rejected"].items() if r},
        **{f: {str(k): v for k, v in sorted(fused[f].items())} for f in FIELDS},
    }


def build(book: Book, layout: dict[str, Any]) -> dict[str, Any]:
    cfg = settings(book)
    lessons: dict[str, Any] = {}
    for r in layout["lessons"]:
        if not r["pages_pdf"]:
            continue
        a, z = r["pages_pdf"][0], r["pages_pdf"][1]
        lessons[r["id"]] = {"pages_pdf": [a, z], **_plain(fuse(book, a, z, cfg))}
    return {"book": book.id, "lessons": lessons}


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    ls = result["lessons"]

    def count(status: str) -> int:
        return sum(v == status for lesson in ls.values() for f in FIELDS for v in lesson[f].values())

    return {
        "lessons": len(ls),
        "by_status": {s: count(s) for s in STATUSES},
        "review": {k: v["review_pages"] for k, v in ls.items() if v["review_pages"]},
    }
