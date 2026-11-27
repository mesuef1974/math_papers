"""صفحات تمارين كل درس في كتاب الطالب إلى `exercise_pages.json` (أرقام فقط) خارج المستودع.

أول صفحة للدرس في كتاب الطالب من `layout` وجدولي `printed_pages` (صفحة الدليل → المطبوع) و`student_pages` (صفحة ملف الطالب →
المطبوع) بمنطق `student_examples.lesson_pages`، ويمتد إلى أول الدرس التالي، وقسم التمارين يبدأ من أول سطر علامته (`student_examples.end_patterns`). رقم التمرين صندوق OCR رقم وحده (`exercise_badges.exercise_anchors`)، ويُقبل ما دام يكمل سلسلة متزايدة من 1 بقفزة
`exercises.jump` عبر الصفحات؛ التمرين غير المقروء لا تُخمَّن صفحته. القيمة مديات `{first, last, page}` (المطبوع) يقرؤها
`build_course_index` و`write_book_numbers`. الحالة `ok` حين تكتمل السلسلة 1..عدد تمارين الدليل (سجل الدرس `lesson`) بلا فجوة،
وإلا `review` (و`missing` بلا قسم تمارين أو أرقام)، واعتماد المالك تصحيح في `corrections.yaml` (`stage: exercise_pages`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from typing import Any

from apps.knowledge.domain.exercise_pages import compress

from . import student_examples
from .config import Book
from .exercise_badges import exercise_anchors
from .fields import field
from .fusion import settings as fusion_settings
from .lesson import lessons_dir
from .printed_pages import Boxes
from .text import norm

LEADING = re.compile(r"^\.?(\d{1,2})\.(?!\d)")
TRAILING = re.compile(r"(?<![\d.])(\d{1,2})\s?\.$|(?<!\d)\.(\d{1,2})$")
ARABIC = re.compile(r"[ء-ي]")
LAST_SPAN = 14  # أقصى صفحات درس: يمنع ابتلاع مراجعة الوحدة وما بعدها


def marker_bottom(boxes: Boxes, stops: Sequence[re.Pattern[str]]) -> int | None:
    """أعلى سطر علامة التمارين في الصفحة (أسفل صندوقه)، أو None."""
    found = [box for text, box in boxes if any(p.search(norm(text)) for p in stops)]
    return min(found, key=lambda b: b[1])[3] if found else None


def chain(pages: Sequence[tuple[int, set[int]]], jump: int) -> dict[int, int]:
    """رقم التمرين → صفحته: من كل صفحة بترتيبها ما يكمل السلسلة المتزايدة بقفزة لا تتجاوز `jump`."""
    out: dict[int, int] = {}
    last = 0
    for page, numbers in pages:
        for n in sorted(numbers):
            if last < n <= last + jump:
                out[n] = page
                last = n
    return out


def lesson_exercises(
    pages: Sequence[tuple[int, int]],
    boxes_of: Callable[[int], Boxes | None],
    stops: Sequence[re.Pattern[str]],
    cap: int,
    jump: int,
) -> dict[int, int]:
    """رقم التمرين → صفحته المطبوعة. `pages` أزواج (صفحة ملف الطالب، المطبوع)؛ ما قبل علامة التمارين لا يُقرأ."""
    started = False
    seen: list[tuple[int, set[int]]] = []
    for page, printed in pages:
        boxes = boxes_of(page) or []
        top = 0
        if not started:
            bottom = marker_bottom(boxes, stops)
            if bottom is None:
                continue
            started, top = True, bottom
        seen.append((printed, numbers(boxes, cap, top)))
    return chain(seen, jump)


def numbers(boxes: Boxes, cap: int, top: int = 0) -> set[int]:
    """أرقام التمارين تحت `top`: صندوق رقم وحده (`exercise_anchors`)، أو سطر يبدأ بـ «N.» (التمرين مع نصه في صندوق)،
    أو سطر عربي ينتهي بها (الرقم يمين النص). العدد العشري ليس رقم تمرين."""
    below = [(text, box) for text, box in boxes if box[3] > top]
    out = {a["n"] for a in exercise_anchors(below, cap)}
    for text, _ in below:
        line = norm(text).strip()
        found = LEADING.match(line) or (ARABIC.search(line) and TRAILING.search(line))
        if found and 1 <= int(next(g for g in found.groups() if g)) <= cap:
            out.add(int(next(g for g in found.groups() if g)))
    return out


def spans(starts: Sequence[int | None], printed: Sequence[int]) -> list[list[tuple[int, int]]]:
    """صفحات كل درس (ملف، مطبوع) من أول مطبوعه إلى ما قبل أول الدرس التالي (دليل العاشر لا يضمّن صفحات التمارين).
    `printed` أزواج المطبوع المعروفة تُمرَّر مرتبة؛ الدرس الأخير ينتهي بعد `LAST_SPAN` صفحة على الأكثر."""
    out = []
    for i, start in enumerate(starts):
        if start is None:
            out.append([])
            continue
        after = min((s for s in starts[i + 1 :] if s is not None and s > start), default=start + LAST_SPAN)
        out.append([p for p in printed if start <= p < min(after, start + LAST_SPAN)])
    return out


def status(found: dict[int, int], total: int) -> str:
    if not found:
        return "missing"
    return "ok" if total and sorted(found) == list(range(1, total + 1)) else "review"


def totals(book: Book, lessons: Sequence[str]) -> dict[str, int]:
    """درس → عدد تمارينه من سجل الدرس المعتمد (`ok`)؛ الغائب صفر."""
    out = {}
    for code in lessons:
        path = lessons_dir(book) / f"lesson_{code.replace('.', '_')}.json"
        record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        exercises = record.get("exercises") or {}
        value = exercises.get("value") or []
        out[code] = max(value, default=0) if exercises.get("status") == "ok" else 0
    return out


def build(
    book: Book,
    layout: dict[str, Any],
    guide_table: dict[int, int],
    student_table: dict[int, int],
    boxes_of: Callable[[int], Boxes | None],
) -> dict[str, Any]:
    cfg = student_examples.settings(book)
    fusion = fusion_settings(book)
    stops = student_examples.end_patterns(book, cfg)
    if not stops:
        raise student_examples.StudentExamplesError(
            "لا علامة تمارين: markers.exercises أو student_examples.end_patterns"
        )
    inverse = {printed: page for page, printed in student_table.items()}
    known = totals(book, [r["id"] for r in layout["lessons"]])
    result: dict[str, Any] = {"book": book.id, "lessons": {}}
    firsts = []
    for r in layout["lessons"]:
        _, span, _ = student_examples.lesson_pages(r["pages_pdf"], guide_table, inverse)
        firsts.append(span[0] if span else None)
    for r, wanted in zip(layout["lessons"], spans(firsts, sorted(inverse)), strict=True):
        total = known[r["id"]]
        cap = min(total or fusion["max_exercise"], fusion["max_exercise"])
        pages = [(inverse[p], p) for p in wanted]
        found = lesson_exercises(pages, boxes_of, stops, cap, fusion["jump"]["exercises"])
        result["lessons"][r["id"]] = field(
            compress(found),
            "derived",
            status(found, total),
            total=total,
            unread=[n for n in range(1, max(total, max(found, default=0)) + 1) if n not in found],
        )
    return result


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    ls = result["lessons"]
    return {
        "lessons": len(ls),
        **{s: [k for k, v in ls.items() if v["status"] == s] for s in ("review", "missing")},
        "ok": sum(v["status"] == "ok" for v in ls.values()),
        "unread": sum(len(v["unread"]) for v in ls.values()),
    }
