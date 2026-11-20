"""ربط الأمثلة بتدريباتها من سطر «حاول أن تحل التمرين N» الذي يختم كل مثال في صفحات الشرح (كالثاني عشر).

الإحالة في هذا الكتاب من المثال إلى التدريب لا العكس: صفحات التمارين بلا إحالة، والمثال ينتهي بسطر أزرق رقمه كثيرًا ما يضيع
من OCR الصفحة كلها. لكل درس، في صفحاته من أول مثال إلى نهايته وبترتيب الأسطر من الأعلى: سطر «مثال» وحده (`examples.LABEL_LINE`)
يفتح المثال التالي المقبول في `examples.json` على صفحته، وسطر «حاول أن تحل» (`exercise_try.marker`) يُنسب إلى المثال المفتوح.
عند أول كل صفحة يُعاد المثال المفتوح إلى آخر مثال بدأ قبلها (`start` في `examples.json`)، فكلمة فاتت OCR لا تزيح ما بعد صفحتها.
رقم التدريب في الطرف الأيسر من صندوق السطر نفسه، والتعرّف على السطر كله يُسقطه (قياس الثاني عشر: صندوق السطر 16 حرفًا عربيًا
بلا رقم، ولا حبر يساره)؛ فيُقصّ الطرف بعرض `slice` من ارتفاع السطر من صورة الصفحة (`dirs.render`) ويُقرأ بالتعرّف وحده
(`ocr.read_scored`)، ويُقبل ما ثقته `min_score` فأكثر، وإلا فمن نص الصندوق. الأرقام 1..`exercises.max`، و«12-14» مدى. المخرج بمخطط `exercise_links.json` (أرقام وحدها)، و`pages` صفحة
السطر، ومع كل درس تشخيصه: `lines` و`unread` و`from_text` و`monotone` (أول تدريب لكل مثال يتزايد بترتيب الأمثلة) و`crowded`
(مثال أخذ أكثر من سطر: فات OCR سطر «مثال» قبله)، وحالته `review` دائمًا (أو `missing` بلا رقم مقروء): الربط مقروء من صورة، ولا يصير `ok` إلا بتصحيح المالك.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .config import Book
from .examples import LABEL_LINE
from .fields import field
from .fusion import settings as fusion_settings
from .printed_pages import Boxes
from .text import norm, squash

DEFAULTS: dict[str, Any] = {"marker": "حاول أن تحل", "slice": 1.2, "min_score": 0.6}
RANGE = 10  # أطول مدى مقبول «a-b»
Ocr = Callable[[Any], tuple[str, float]]  # (نص، ثقة)


def settings(book: Book) -> dict[str, Any]:
    return {**DEFAULTS, **(book.get("exercise_try") or {})}


def exercise_numbers(text: str, cap: int) -> list[int]:
    """أرقام التدريبات 1..cap في نص («33»، «12 و13»، «12-14» مدى)؛ ما فوق السقف يُسقط."""
    out: set[int] = set()
    clean = norm(text)
    for a, b in re.findall(r"(\d+)\s*[-–]\s*(\d+)", clean):
        lo, hi = int(a), int(b)
        if 1 <= lo < hi <= cap and hi - lo <= RANGE:
            out |= set(range(lo, hi + 1))
    out |= {int(x) for x in re.findall(r"\d+", clean) if 1 <= int(x) <= cap}
    return sorted(out)


def events(boxes: Boxes, marker: str) -> list[tuple[str, list[int], str]]:
    """أسطر الصفحة المعنية من الأعلى: ("label"|"try", صندوق، نص)."""
    label = re.compile(LABEL_LINE)
    key = squash(marker)
    out = []
    for text, box in boxes:
        if label.match(norm(text)):
            out.append(("label", box, text))
        elif key in squash(text):
            out.append(("try", box, text))
    return sorted(out, key=lambda e: (e[1][1], -e[1][2]))


def read_try(
    image: Any, box: list[int], text: str, ocr: Ocr, cap: int, cfg: dict[str, Any]
) -> tuple[list[int], bool]:
    """(أرقام سطر «حاول أن تحل»، هل قُرئت من الصورة): من طرف الصندوق الأيسر إن وُجدت الصورة ووثق القارئ، وإلا من نصه."""
    if image is not None:
        x0, y0, x1, y1 = box
        h = y1 - y0
        pad = max(2, h // 12)
        crop = image.crop(
            (max(0, x0 - pad), max(0, y0 - pad), min(x1, x0 + round(cfg["slice"] * h)), y1 + pad)
        )
        read, score = ocr(crop)
        got = exercise_numbers(read or "", cap)
        if got and score >= cfg["min_score"]:
            return got, True
    return exercise_numbers(text, cap), False


def link(pages: dict[int, list[tuple[str, list[int], list[int]]]], starts: dict[int, int]) -> dict[str, Any]:
    """ربط درس واحد. `pages`: صفحة → أحداثها بالترتيب ("label"|"try"، صندوق، أرقام)، و`starts`: مثال مقبول → صفحة بدايته."""
    order = sorted(starts, key=lambda x: (starts[x], x))
    rows: dict[int, dict[str, set[int]]] = {x: {"exercises": set(), "pages": set()} for x in order}
    taken: dict[int, int] = {}
    unlinked: set[int] = set()
    lines = unread = 0
    for page in sorted(pages):
        before = [x for x in order if starts[x] < page]
        fresh = [x for x in order if starts[x] == page]
        current = before[-1] if before else None
        for kind, _, numbers in pages[page]:
            if kind == "label":
                if fresh:
                    current = fresh.pop(0)
                continue
            lines += 1
            if not numbers:
                unread += 1
            elif current is None:
                unlinked |= set(numbers)
            else:
                rows[current]["exercises"] |= set(numbers)
                taken[current] = taken.get(current, 0) + 1
                rows[current]["pages"].add(page)
    linked = {n for row in rows.values() for n in row["exercises"]}
    tried = [min(rows[x]["exercises"]) for x in order if rows[x]["exercises"]]
    return {
        "links": [
            {"example": x, "exercises": sorted(rows[x]["exercises"]), "pages": sorted(rows[x]["pages"])}
            for x in sorted(order)
        ],
        "unlinked": sorted(unlinked - linked),
        "lines": lines,
        "unread": unread,
        "monotone": all(a <= b for a, b in zip(tried, tried[1:], strict=False)),
        "crowded": sorted(x for x, n in taken.items() if n > 1),
    }


def build(
    book: Book,
    layout: dict[str, Any],
    examples: dict[str, Any],
    image_of: Callable[[int], Any],
    boxes_of: Callable[[int], Boxes | None],
    ocr: Ocr,
) -> dict[str, Any]:
    """`image_of(صفحة)` صورتها (Pillow) أو None، و`boxes_of(صفحة)` صناديق أسطرها أو None، و`ocr(صورة) -> (نص، ثقة)`."""
    cfg = settings(book)
    cap = fusion_settings(book)["max_exercise"]
    result: dict[str, Any] = {"book": book.id, "lessons": {}}
    for r in layout["lessons"]:
        known = examples["lessons"].get(r["id"], {}).get("value") or []
        starts = {e["n"]: e["start"] for e in known}
        pages: dict[int, list[tuple[str, list[int], list[int]]]] = {}
        fallback = 0
        if r["pages_pdf"] and starts:
            last = r["pages_pdf"][1]
            for page in range(min(starts.values()), last + 1):
                boxes = boxes_of(page) or []
                found = events(boxes, cfg["marker"])
                if not found:
                    continue
                image = image_of(page) if any(kind == "try" for kind, _, _ in found) else None
                pages[page] = []
                for kind, box, text in found:
                    numbers, seen = (
                        read_try(image, box, text, ocr, cap, cfg) if kind == "try" else ([], False)
                    )
                    fallback += kind == "try" and bool(numbers) and not seen
                    pages[page].append((kind, box, numbers))
        got = link(pages, starts)
        result["lessons"][r["id"]] = field(
            got["links"] if starts else [],
            "derived",
            "review" if any(row["exercises"] for row in got["links"]) else "missing",
            unlinked=got["unlinked"],
            lines=got["lines"],
            unread=got["unread"],
            from_text=fallback,
            monotone=got["monotone"],
            crowded=got["crowded"],
        )
    return result


def readable(entry: dict[str, Any] | None) -> bool:
    """هل في الدرس سطر «حاول أن تحل» واحد مربوط فأكثر (فيُؤخذ ربطه منه لا من الشارات أو التجاور)."""
    return bool(entry) and any(row["exercises"] for row in entry.get("value") or [])


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    ls = result["lessons"]
    rows = [row for v in ls.values() for row in v["value"]]
    return {
        "lessons": len(ls),
        "examples": len(rows),
        "linked_examples": sum(bool(row["exercises"]) for row in rows),
        "lines": sum(v["lines"] for v in ls.values()),
        "unread": sum(v["unread"] for v in ls.values()),
        "from_text": sum(v["from_text"] for v in ls.values()),
        "not_monotone": [k for k, v in ls.items() if not v["monotone"]],
        "crowded": [k for k, v in ls.items() if v["crowded"]],
        "missing": [k for k, v in ls.items() if v["status"] == "missing"],
    }
