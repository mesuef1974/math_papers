"""ربط الأمثلة بتدريباتها من سطر «حاول أن تحل التمرين N» الذي يختم كل مثال في صفحات الشرح (كالثاني عشر).

الإحالة في هذا الكتاب من المثال إلى التدريب لا العكس: صفحات التمارين بلا إحالة، والمثال ينتهي بسطر أزرق رقمه كثيرًا ما يضيع
من OCR الصفحة كلها. لكل درس، في صفحاته (`layout`) وبترتيب الأسطر من الأعلى صفحةً بعد صفحة، الأمثلة تُعدّ من الأسطر نفسها:
سطر «مثال» وحده (`examples.LABEL_LINE`) يفتح المثال التالي، وسطر «حاول أن تحل» (`exercise_try.marker`) يُنسب إلى المثال المفتوح،
فإن كان قد أخذ سطره (أو لا مثال مفتوح) فقد فات OCR سطر «مثال» قبله، فيفتح السطر نفسه المثال التالي: لكل مثال سطر واحد، والسطر الذي لا رقم فيه مقروءًا لا يأخذ مكان سطر مثاله (قد لا يكون سطره).
لا يُؤخذ العدّ ولا الصفحات من `examples.json`: قياس الثاني عشر أن الدليل يعدّ فيه أمثلة ليست في كتاب الطالب (3.4: تسعة والكتاب
ثلاثة) ويضع بداياتها في غير صفحاتها. والأمثلة المفتوحة بعد آخر سطر «حاول أن تحل» (عنوان «مثال» في صفحات التمارين) تُسقط.
رقم التدريب في الطرف الأيسر من صندوق السطر نفسه، والتعرّف على السطر كله يُسقطه (قياس الثاني عشر: صندوق السطر 16 حرفًا عربيًا
بلا رقم، ولا حبر يساره)؛ فيُقصّ الطرف من صورة الصفحة (`dirs.render`) بكل عرض في `slices` (أضعاف ارتفاع السطر) ويُقرأ
بالتعرّف وحده (`ocr.read_scored`)، ويُقبل ما ثقته `min_score` فأكثر، والقراءة ما تكرر أكثر (ثم الأوثق)، وإلا فمن نص الصندوق.
قياس الثاني عشر: القصّ الأضيق يبتر العدد ذا الخانتين (1 بدل 10) والأعرض يضيف خانة من حبر بعد الرقم (49 بدل 4). والمثال الذي
يخالف رقمه تزايد جاريه يأخذ قراءة أخرى لسطره تلائمهما إن وُجدت (`repaired`). الأرقام 1..`exercises.max`، و«12-14» مدى. المخرج بمخطط `exercise_links.json` (أرقام وحدها)، و`pages` صفحة
السطر، ومع كل درس تشخيصه: `lines` و`unread` و`from_text` و`labels` (أسطر «مثال») و`opened` (أمثلة فتحها سطر «حاول أن تحل»
لأن سطر «مثال» قبله فات) و`monotone` (أول تدريب لكل مثال يتزايد بترتيب الأمثلة)، وحالته `review` دائمًا (أو `missing` بلا رقم
مقروء): الربط مقروء من صورة، ولا يصير `ok` إلا بتصحيح المالك.
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

DEFAULTS: dict[str, Any] = {"marker": "حاول أن تحل", "slices": [0.8, 1.0, 1.2], "min_score": 0.6}
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
) -> tuple[list[list[int]], bool]:
    """(قراءات سطر «حاول أن تحل» مرتبة، أولها المختارة؛ هل قُرئت من الصورة): من طرف الصندوق الأيسر بكل عرض في `slices`
    إن وُجدت الصورة ووثق القارئ (الأكثر تكرارًا ثم الأوثق)، وإلا من نص الصندوق."""
    if image is not None:
        x0, y0, x1, y1 = box
        h = y1 - y0
        pad = max(2, h // 12)
        votes: dict[tuple[int, ...], list[float]] = {}
        for width in cfg["slices"]:
            crop = image.crop((max(0, x0 - pad), max(0, y0 - pad), min(x1, x0 + round(width * h)), y1 + pad))
            read, score = ocr(crop)
            got = exercise_numbers(read or "", cap)
            if got and score >= cfg["min_score"]:
                votes.setdefault(tuple(got), []).append(score)
        if votes:
            ranked = sorted(votes, key=lambda k: (-len(votes[k]), -max(votes[k])))
            return [list(k) for k in ranked], True
    got = exercise_numbers(text, cap)
    return ([got] if got else []), False


Event = tuple[str, list[int], list[list[int]]]  # ("label"|"try"، صندوق، قراءات السطر مرتبة)


def link(pages: dict[int, list[Event]]) -> dict[str, Any]:
    """ربط درس واحد. `pages`: صفحة → أحداثها من الأعلى؛ الأمثلة تُعدّ من الأحداث نفسها."""
    rows: list[dict[str, Any]] = []
    labels = opened = lines = unread = 0
    for page in sorted(pages):
        for kind, _, reads in pages[page]:
            if kind == "label":
                labels += 1
                rows.append({"reads": [], "page": None})
                continue
            lines += 1
            if not reads:
                unread += 1
                continue
            if not rows or rows[-1]["reads"]:
                opened += 1
                rows.append({"reads": [], "page": None})
            rows[-1]["reads"], rows[-1]["page"] = reads, page
    while rows and not rows[-1]["reads"]:  # «مثال» بلا سطر بعده في آخر الدرس: عنوان في صفحات التمارين
        rows.pop()
    chosen = [row["reads"][0] if row["reads"] else [] for row in rows]
    for _ in rows:  # حتى الثبات: إصلاح جارٍ لاحق قد يفتح مكانًا لبديل سابق (حدّه عدد الأمثلة)
        changed = False
        for i, row in enumerate(rows):
            if len(row["reads"]) < 2:
                continue
            lo = max((min(c) for c in chosen[:i] if c), default=0)
            hi = min((min(c) for c in chosen[i + 1 :] if c), default=10**6)
            if lo <= min(chosen[i]) <= hi:
                continue
            fit = next((c for c in row["reads"] if c != chosen[i] and lo <= min(c) <= hi), None)
            if fit:
                chosen[i], changed = fit, True
        if not changed:
            break
    repaired = sum(bool(row["reads"]) and c != row["reads"][0] for row, c in zip(rows, chosen, strict=True))
    firsts = [min(c) for c in chosen if c]
    return {
        "links": [
            {"example": i, "exercises": sorted(set(c)), "pages": [row["page"]] if c else []}
            for i, (row, c) in enumerate(zip(rows, chosen, strict=True), start=1)
        ],
        "lines": lines,
        "unread": unread,
        "labels": labels,
        "opened": opened,
        "repaired": repaired,
        "monotone": all(a <= b for a, b in zip(firsts, firsts[1:], strict=False)),
    }


def build(
    book: Book,
    layout: dict[str, Any],
    image_of: Callable[[int], Any],
    boxes_of: Callable[[int], Boxes | None],
    ocr: Ocr,
) -> dict[str, Any]:
    """`image_of(صفحة)` صورتها (Pillow) أو None، و`boxes_of(صفحة)` صناديق أسطرها أو None، و`ocr(صورة) -> (نص، ثقة)`."""
    cfg = settings(book)
    cap = fusion_settings(book)["max_exercise"]
    result: dict[str, Any] = {"book": book.id, "lessons": {}}
    for r in layout["lessons"]:
        pages: dict[int, list[Event]] = {}
        fallback = 0
        if r["pages_pdf"]:
            first, last = r["pages_pdf"]
            for page in range(first, last + 1):
                found = events(boxes_of(page) or [], cfg["marker"])
                if not found:
                    continue
                image = image_of(page) if any(kind == "try" for kind, _, _ in found) else None
                pages[page] = []
                for kind, box, text in found:
                    reads, seen = read_try(image, box, text, ocr, cap, cfg) if kind == "try" else ([], False)
                    fallback += kind == "try" and bool(reads) and not seen
                    pages[page].append((kind, box, reads))
        got = link(pages)
        result["lessons"][r["id"]] = field(
            got["links"],
            "derived",
            "review" if any(row["exercises"] for row in got["links"]) else "missing",
            unlinked=[],
            lines=got["lines"],
            unread=got["unread"],
            from_text=fallback,
            labels=got["labels"],
            opened=got["opened"],
            repaired=got["repaired"],
            monotone=got["monotone"],
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
        "opened": [k for k, v in ls.items() if v["opened"]],
        "repaired": sum(v["repaired"] for v in ls.values()),
        "missing": [k for k, v in ls.items() if v["status"] == "missing"],
    }
