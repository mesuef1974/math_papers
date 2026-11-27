"""صفحات تمارين كل درس في كتاب الطالب إلى `exercise_pages.json` (أرقام فقط) خارج المستودع.

أول صفحة للدرس في كتاب الطالب من `layout` وجدولي `printed_pages` (صفحة الدليل → المطبوع) و`student_pages` (صفحة ملف الطالب →
المطبوع) بمنطق `student_examples.lesson_pages`، ويمتد إلى أول الدرس التالي، وقسم التمارين يبدأ من أول سطر علامته (`student_examples.end_patterns`). رقم التمرين صندوق OCR رقم وحده (`exercise_badges.exercise_anchors`)، ويُقبل ما دخل أطول سلسلة متزايدة عبر الصفحات
(`chain`)، والفجوة داخل صفحة واحدة تُسدّ (`fill`)؛
والرقم الذي يسقطه التعرّف على السطر العربي يُقرأ ثانية من الكتلة اليمنى لصورة السطر (`reread`)؛ التمرين غير المقروء لا تُخمَّن صفحته. القيمة مديات `{first, last, page}` (المطبوع) يقرؤها
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
NUMBER = re.compile(r"^\.?\s?(\d{1,2})\s?\.?$")
INK = 160  # أدنى سطوع لا يُعدّ حبرًا
TAIL_GAP = 0.25  # فراغ يفصل رقم التمرين عن أول كلمة (نصيب من ارتفاع السطر)
TAIL_WIDTH = 1.6  # أقصى عرض لكتلة رقم
MIN_SCORE = 0.8
Ocr = Callable[[Any], tuple[str, float]]
GAP = 3  # مضاعف `exercises.jump`: القراءة تُسقط أرقامًا متتالية
LAST_SPAN = 14  # أقصى صفحات درس: يمنع ابتلاع مراجعة الوحدة وما بعدها


def marker_bottom(boxes: Boxes, stops: Sequence[re.Pattern[str]]) -> int | None:
    """أعلى سطر علامة التمارين في الصفحة (أسفل صندوقه)، أو None."""
    found = [box for text, box in boxes if any(p.search(norm(text)) for p in stops)]
    return min(found, key=lambda b: b[1])[3] if found else None


def chain(pages: Sequence[tuple[int, set[int]]], jump: int) -> dict[int, int]:
    """رقم التمرين → صفحته: أطول سلسلة متزايدة بترتيب الصفحات لا تقفز بين متتاليين أكثر من `jump`، فالرقم الدخيل لا
    يقطع ما بعده. عند التساوي تُقدَّم الأرقام الأصغر قفزًا."""
    items = [(n, page) for page, numbers in pages for n in sorted(numbers)]
    best: list[tuple[int, int, int]] = []  # (الطول، ‎-مجموع القفزات، السابق)
    for i, (n, _) in enumerate(items):
        start = (1, -n, -1) if n <= jump else (0, 0, -1)
        links = (
            (best[j][0] + 1, best[j][1] - (n - m), j)
            for j, (m, _) in enumerate(items[:i])
            if best[j][0] and 0 < n - m <= jump
        )
        best.append(max([start, *links]))
    i = max(range(len(items)), key=lambda k: best[k][:2], default=-1)
    out: dict[int, int] = {}
    while i >= 0 and best[i][0]:
        out[items[i][0]] = items[i][1]
        i = best[i][2]
    return dict(sorted(out.items()))


def fill(found: dict[int, int], start: int | None = None) -> dict[int, int]:
    """يسدّ الفجوة بين رقمين في صفحة واحدة: التمارين متتالية فصفحة ما بينهما هي نفسها بلا تخمين.
    `start` صفحة علامة التمارين: هي موضع «ما قبل 1» فتُسدّ بها بداية السلسلة."""
    out = dict(found)
    known = {**found, 0: start} if start and found else found
    ordered = sorted(known)
    for a, z in zip(ordered, ordered[1:], strict=False):
        if known[a] == known[z]:
            out.update(dict.fromkeys(range(a + 1, z), known[a]))
    return dict(sorted(out.items()))


def lesson_exercises(
    pages: Sequence[tuple[int, int]],
    boxes_of: Callable[[int], Boxes | None],
    stops: Sequence[re.Pattern[str]],
    cap: int,
    jump: int,
    second: Callable[[int, Boxes, int], set[int]] | None = None,
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
        seen.append((printed, numbers(boxes, cap, top) | (second(page, boxes, top) if second else set())))
    return fill(chain(seen, jump), seen[0][0] if seen else None)


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


def tail_span(inked: Sequence[int], gap: int) -> tuple[int, int] | None:
    """[x0, x1) آخر كتلة حبر يمينًا في إسقاط أعمدة سطر: تنتهي يسارًا عند أول فراغ بعرض `gap` فأكثر."""
    right = next((x + 1 for x in range(len(inked) - 1, -1, -1) if inked[x]), None)
    if right is None:
        return None
    left, blank = right - 1, 0
    for x in range(right - 2, -1, -1):
        blank = 0 if inked[x] else blank + 1
        if blank >= gap:
            break
        if inked[x]:
            left = x
    return left, right


def reread(image: Any, boxes: Boxes, read: Ocr, cap: int, top: int = 0) -> set[int]:
    """أرقام التمارين التي أسقطها التعرّف على السطر العربي كله: الكتلة اليمنى من صندوق السطر تُقصّ وتُقرأ وحدها."""
    out: set[int] = set()
    for text, (x0, y0, x1, y1) in boxes:
        h = y1 - y0
        if y1 <= top or h <= 0 or not ARABIC.search(text):
            continue
        strip = image.crop((x0, y0, x1, y1)).convert("L").point(lambda v: 255 * (v < INK))
        span = tail_span([1 if v else 0 for v in strip.getprojection()[0]], max(2, round(TAIL_GAP * h)))
        if span is None or span[1] - span[0] > TAIL_WIDTH * h:
            continue
        pad = max(2, h // 8)
        got, score = read(image.crop((x0 + span[0] - pad, y0, x0 + span[1] + pad, y1)))
        found = NUMBER.match(norm(got or "").strip())
        if found and score >= MIN_SCORE and 1 <= int(found.group(1)) <= cap:
            out.add(int(found.group(1)))
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
    image_of: Callable[[int], Any] | None = None,
    read: Ocr | None = None,
) -> dict[str, Any]:
    """`image_of(صفحة ملف الطالب)` صورتها أو None و`read(مقطع) -> (نص، ثقة)`: بدونهما لا قراءة ثانية."""
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

        def second(page: int, boxes: Boxes, top: int, cap: int = cap) -> set[int]:
            image = image_of(page) if image_of else None
            return reread(image, boxes, read, cap, top) if image is not None and read else set()

        found = lesson_exercises(pages, boxes_of, stops, cap, GAP * fusion["jump"]["exercises"], second)
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
