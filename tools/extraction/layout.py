"""حدود الدروس ونوع كل صفحة بلا نموذج لغة: قواعد حتمية على نص OCR، كلها مصدرها derived.

الدرس يُعرف بإحدى طريقتين (layout.anchor): صفحة افتتاحه (opener)، أو صفحة جدول تحليل التمارين (analysis) وافتتاحيته أقرب
صفحة تحمل علامة الافتتاح قبله ضمن `opener_window`. ونهايته (layout.end): صفحة الاختبار التي تحمل markers.quiz بعد الجدول (quiz)،
أو آخر صفحة قبل أول علامة وقف (markers.end_stop: مراجعة الوحدة مثلًا) أو قبل افتتاحية الدرس التالي (next_opener).
كل سجل درس يحمل checks وstatus (ok إن نجحت كلها وإلا review). المدخل: نصوص الصفحات بعد squash؛ المخرج قابل للحفظ JSON.
"""

from __future__ import annotations

import re
from typing import Any

from .config import Book
from .fields import field
from .text import squash

Pages = dict[int, str]


def load_pages(book: Book) -> Pages:
    return {
        n: squash(book.page_text(n))
        for n in range(1, book["pages"] + 1)
        if (book.dir("ocr") / f"{n:04d}.txt").exists()
    }


def _has(text: str, marker: str) -> bool:
    return squash(marker) in text


def _std(book: Book) -> re.Pattern[str]:
    return re.compile(book["standards"]["pattern"], re.IGNORECASE)


def _printed_id(book: Book, text: str) -> tuple[int, int] | None:
    """(الوحدة، الدرس) المطبوعان في افتتاحية الدرس (layout.id_pattern بمجموعتين) إن وُجدا."""
    pat = book["layout"].get("id_pattern")
    m = re.search(pat, text) if pat else None
    return (int(m[1]), int(m[2])) if m else None


def openers(pages: Pages, book: Book) -> list[int]:
    """صفحات الافتتاح المرشَّحة بعلامة markers.opener (وبرمز معيار إن طُلب layout.opener_needs_standard)."""
    marker = squash(book["markers"]["opener"])
    need = book["layout"].get("opener_needs_standard", False)
    std = _std(book)
    return sorted(n for n, t in pages.items() if marker in t and (not need or std.search(t)))


def _end_stop(pages: Pages, book: Book, after: int, before: int) -> int | None:
    stops = [squash(s) for s in book["markers"].get("end_stop", [])]
    return next((n for n in range(after + 1, before) if any(s in pages.get(n, "") for s in stops)), None)


def lessons(pages: Pages, book: Book, analysis_pages: list[int] | None = None) -> list[dict[str, Any]]:
    cfg = book["layout"]
    last_page = max(pages, default=0)
    out: list[dict[str, Any]] = []
    if cfg["anchor"] == "analysis":
        marker = squash(book["markers"]["analysis"])
        tables = sorted(analysis_pages or [n for n, t in pages.items() if marker in t])
        ov = openers(pages, book)
        lo, hi = cfg["opener_window"]
        qmark = squash(book["markers"]["quiz"]) if cfg["end"] == "quiz" else None
        for t in tables:
            opener = max((n for n in ov if t - hi <= n <= t - lo), default=None)
            quiz = next(
                (
                    n
                    for n in range(t + 1, t + cfg.get("quiz_window", 6) + 1)
                    if qmark and qmark in pages.get(n, "")
                ),
                None,
            )
            out.append({"table": t, "opener": opener, "quiz": quiz, "end": quiz})
    else:
        ov = openers(pages, book)
        for i, o in enumerate(ov):
            nxt = ov[i + 1] if i + 1 < len(ov) else last_page + 1
            stop = _end_stop(pages, book, o, nxt)
            end = (stop - 1) if stop else nxt - 1
            out.append(
                {"table": None, "opener": o, "quiz": None, "end": end, "ended_by": "stop" if stop else "next"}
            )
    for i, rec in enumerate(out, 1):
        rec["ordinal"] = i
        rec["pages_pdf"] = [rec["opener"], rec["end"]] if rec["opener"] and rec["end"] else None
    _number(out, pages, book)
    return out


def _number(out: list[dict[str, Any]], pages: Pages, book: Book) -> None:
    """يرقّم بالرقم المطبوع في الافتتاحية إن كان متفردًا ومتصاعدًا في كل الدروس (source guide)، وإلا بفجوة الوحدات (derived)."""
    printed = [_printed_id(book, pages.get(r["opener"], "")) if r["opener"] else None for r in out]
    keys = [p for p in printed if p]
    if out and len(keys) == len(out) and keys == sorted(set(keys)):
        for r, (unit, lesson) in zip(out, keys, strict=True):
            r.update(id=book.lesson_id(unit, lesson), unit=unit, id_source="guide")
        return
    gap = book["layout"].get("unit_gap", 8)
    unit, k, prev_end = 1, 0, None
    for r in out:
        if prev_end is not None and r["opener"] and r["opener"] - prev_end > gap:
            unit, k = unit + 1, 0
        k += 1
        r.update(unit=unit, id=book.lesson_id(unit, k), id_source="derived")
        prev_end = r["end"] or prev_end


def check(rec: dict[str, Any], pages: Pages, book: Book, prev: dict[str, Any] | None) -> dict[str, bool]:
    cfg = book["layout"]
    m = book["markers"]
    span = rec["pages_pdf"]
    opener_text = pages.get(rec["opener"], "") if rec["opener"] else ""
    # أين يُطبع رمز المعيار: في الافتتاحية (الثاني عشر) أو في صفحة اختبار الدرس (العاشر)
    std_page = rec["quiz"] if cfg.get("standard_on", "opener") == "quiz" else rec["opener"]
    std_text = pages.get(std_page, "") if std_page else ""
    c = {
        "has_span": span is not None,
        "opener_has_objective": squash(m["objective_label"]) in opener_text
        or squash(m["objective_intro"]) in opener_text,
        "standard_found": bool(_std(book).search(std_text)),
        "length_ok": bool(span)
        and cfg.get("min_span", 3) <= span[1] - span[0] + 1 <= cfg.get("max_span", 25),
        "no_overlap": prev is None or not prev["pages_pdf"] or not span or span[0] > prev["pages_pdf"][1],
    }
    rec["checks"] = c
    rec["status"] = "ok" if all(c.values()) else "review"
    rec["source"] = "derived"
    return c


def page_types(pages: Pages, ls: list[dict[str, Any]], book: Book) -> dict[int, dict[str, Any]]:
    """صفحات الدروس مؤكدة (ok)؛ ما خارجها يوسَم بموضعه فقط مع تلميحات علامات النص وحالته review."""
    spans = [r for r in ls if r["pages_pdf"]]
    if not spans:
        return {n: {"type": "unknown", "source": "derived", "status": "review"} for n in pages}
    first, last = spans[0]["opener"], spans[-1]["end"]
    marks = book["markers"]
    hints_sq = {"objective": [squash(marks["objective_label"])], "overview": [squash(marks["opener"])]}
    hints_sq |= {
        k: [squash(v)] for k, v in marks.items() if k in ("review", "analysis", "quiz") and isinstance(v, str)
    }
    hints_sq["end_stop"] = [squash(s) for s in marks.get("end_stop", [])]
    types: dict[int, dict[str, Any]] = {}
    for n, t in pages.items():
        hints = [k for k, ws in hints_sq.items() if any(w in t for w in ws)]
        kind, status = None, "review"
        for r in spans:
            a, z = r["pages_pdf"]
            if a <= n <= z:
                kind = (
                    "lesson_opener"
                    if n == a
                    else "analysis_table"
                    if n == r["table"]
                    else "lesson_quiz"
                    if n == r["quiz"]
                    else "lesson_body"
                )
                status, hints = "ok", []
                break
        if kind is None:
            if n < first:
                kind = "pre_lesson"
            elif n > last:
                kind = "post_lesson"
            else:
                before = max((r for r in spans if r["pages_pdf"][1] < n), key=lambda r: r["pages_pdf"][1])
                after = min((r for r in spans if r["opener"] > n), key=lambda r: r["opener"])
                kind = "interlesson" if before["unit"] == after["unit"] else "unit_gap"
        types[n] = {
            "type": kind,
            "source": "derived",
            "status": status,
            **({"hints": hints} if hints else {}),
        }
    return types


def build(book: Book, pages: Pages | None = None, analysis_pages: list[int] | None = None) -> dict[str, Any]:
    pages = pages if pages is not None else load_pages(book)
    ls = lessons(pages, book, analysis_pages)
    prev = None
    for r in ls:
        check(r, pages, book, prev)
        prev = r
    return {"book": book.id, "lessons": ls, "pages": page_types(pages, ls, book)}


def summarize(layout: dict[str, Any]) -> dict[str, Any]:
    ls = layout["lessons"]
    counts: dict[str, int] = {}
    for v in layout["pages"].values():
        counts[v["type"]] = counts.get(v["type"], 0) + 1
    return {
        "lessons": len(ls),
        "ok": sum(r["status"] == "ok" for r in ls),
        "review": [r["id"] for r in ls if r["status"] != "ok"],
        "page_types": counts,
        "span_field": field([r["pages_pdf"] for r in ls], "derived", "ok" if ls else "missing"),
    }
