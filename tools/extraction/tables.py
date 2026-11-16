"""جدول «تحليل التمارين» في دليل المعلم: صفوف (المثال، التمارين، العمق المعرفي، المعيار) بلا نموذج لغة.

صناديق كلمات OCR تحدد أعمدة الجدول من ترويسته، والمثال المدموج رأسيًا بين صفوف يُحسب من خطوط الجدول الأفقية في صورة الصفحة.
كل صفحة جدول تُكتب في `dirs.tables/NNNN.json` بشكل `{"rows": [...], "task_guide": {...}}`، وهو ما يقرؤه layout (anchor=analysis).
الإعداد `tables` في book.yaml اختياري (انظر DEFAULTS)؛ numpy وPillow يُستوردان كسولين وغيابهما يعطل خطوط الجدول وحدها.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path
from typing import Any

from .config import Book

CELL = re.compile(r"^[\d\s,،\-–—.]+$")
RLM = chr(0x200F)
Box = list[int]
Boxes = list[tuple[str, Box]]
DEFAULTS: dict[str, Any] = {
    "title": "تحليل التمارين",  # عنوان الجدول المطبوع؛ يُطابَق بلا فراغ
    "headers": {  # نص ترويسة العمود -> مفتاح الحقل
        "المثال": "example",
        "التمارين": "exercises",
        "التمرين": "exercises",
        "العمق المعرفي": "dok",
        "المعيار": "standard",
    },
    "task_levels": {"basic": "أساسي", "advanced": "متقدم"},  # «دليل المهام»: ترويستا المدى
    "header_window": 120,  # أقصى بُعد رأسي للترويسة تحت العنوان (بكسل)
    "row_gap": 110,  # فجوة رأسية بين صفوف الجدول تعني نهايته
    "dark": 215,  # عتبة سواد الخط الأفقي (0 إلى 255)
    "dark_fraction": 0.85,  # أقل نسبة سواد عبر نافذة العمود ليُعدّ الصف خطًا
}


def settings(book: Book) -> dict[str, Any]:
    return {**DEFAULTS, **book.get("tables", {})}


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text.replace(RLM, ""))


def parse_numbers(text: str) -> list[int]:
    out: list[int] = []
    for part in re.split(r"[,،]", text):
        m = re.match(r"^\s*(\d+)\s*[-–—]\s*(\d+)\s*$", part)
        if m and int(m[1]) <= int(m[2]) <= 99:
            out += range(int(m[1]), int(m[2]) + 1)
        elif part.strip().isdigit():
            out.append(int(part))
    return out


def hlines(image: Path, x0: int, x1: int, y0: int, y1: int, cfg: dict[str, Any] | None = None) -> list[int]:
    """مواضع الخطوط الأفقية الرمادية عبر نافذة عمود (متوسط y لكل خط)."""
    import numpy as np
    from PIL import Image

    cfg = cfg or DEFAULTS
    gray = np.asarray(Image.open(image).convert("L"))[y0:y1, x0:x1]
    dark = (gray < cfg["dark"]).mean(axis=1) > cfg["dark_fraction"]
    ys: list[int] = []
    run: list[int] = []
    for i, v in enumerate(dark):
        if v:
            run.append(i)
        elif run:
            ys.append(y0 + sum(run) // len(run))
            run = []
    if run:
        ys.append(y0 + sum(run) // len(run))
    return ys


def task_guide(boxes: Boxes, cfg: dict[str, Any] | None = None) -> dict[str, str]:
    """«دليل المهام»: مدى التمارين الأساسية والمتقدمة تحت ترويستيهما؛ الخلية قد تلتف على سطرين فتُضَم."""
    levels = (cfg or DEFAULTS)["task_levels"]
    heads = {k: b for k, w in levels.items() for t, b in boxes if t == w}
    if not heads:
        return {}
    y0 = max(h[3] for h in heads.values())
    cells = sorted((b[1], b, t) for t, b in boxes if 0 < b[1] - y0 < 130 and CELL.match(t))
    first = [c for c in cells if cells and c[0] - cells[0][0] < 20]
    order = sorted(heads, key=lambda k: (heads[k][0] + heads[k][2]) // 2)
    first_by_x = sorted(first, key=lambda c: c[1][0] + c[1][2])
    out: dict[str, str] = {}
    extent: dict[str, tuple[int, int, int]] = {}  # آخر سطر لكل عمود: (حدّه الأدنى، مداه الأفقي)
    if len(first_by_x) == len(order):  # خلية أولى لكل ترويسة: يُقرَن الأيسر بالأيسر
        for k, (_, b, t) in zip(order, first_by_x, strict=True):
            out[k], extent[k] = t, (b[3], b[0], b[2])
    for y, b, t in cells:
        if any(t == out.get(k) and b[3] == extent[k][0] for k in extent):
            continue
        key = next(
            (k for k, (bottom, x0, x1) in extent.items() if 0 <= y - bottom < 30 and b[0] < x1 and b[2] > x0),
            None,
        )
        if key is None:
            continue
        out[key] = f"{out[key]} {t}"
        extent[key] = (b[3], b[0], b[2])
    return out


def parse(
    boxes: Boxes,
    image: Path,
    cfg: dict[str, Any] | None = None,
    lines: Callable[..., list[int]] | None = None,
) -> list[dict[str, Any]] | None:
    """صفوف الجدول من صناديق صفحة وصورتها؛ None إن لم يُوجد عنوان الجدول أو ترويسته أو خلاياه."""
    cfg = cfg or DEFAULTS
    headers, window = cfg["headers"], cfg["header_window"]
    find_lines = lines or (lambda *a: hlines(image, *a, cfg=cfg))
    title = squash(cfg["title"])
    head = next((b for t, b in boxes if squash(t) == title), None)
    if not head:
        return None
    right = head[2] + 10
    hdr = [(t, b) for t, b in boxes if t in headers and 0 < b[1] - head[3] < window and b[2] <= right]
    if not hdr:
        return None
    cols = {headers[t]: (b[0] + b[2]) // 2 for t, b in hdr}
    top = max(b[3] for _, b in hdr)
    left = min(b[0] for _, b in hdr) - 40
    cells = [(t, b) for t, b in boxes if b[1] > top and left <= b[0] and b[2] <= right and CELL.match(t)]
    cells.sort(key=lambda c: c[1][1])
    # الجدول يتوقف عند أول فجوة رأسية كبيرة بين صفوفه
    kept: list[tuple[str, Box]] = []
    last = top
    for c in cells:
        if c[1][1] - last > cfg["row_gap"]:
            break
        kept.append(c)
        last = c[1][3]
    if not kept:
        return None
    bottom = kept[-1][1][3] + 25
    # الصف = ما بين خطّي الجدول الأفقيين في عمود التمارين (الخلية قد تلتف على سطرين فيُضَمّان)، لا تجميع السطور بالمسافة.
    names = {
        k: [c for c in kept if min(cols, key=lambda n: abs(cols[n] - (c[1][0] + c[1][2]) // 2)) == k]
        for k in cols
    }
    # العمود المدموج رأسيًا (خلية تمتد على عدة صفوف) هو المثال؛ وفي بعض الصفحات تُطبع الترويستان معكوستين
    # فيُحسم بعدد الخلايا لا بنص الترويسة: الأقل خلايا هو المدموج.
    if "example" in cols and "dok" in cols and len(names.get("dok", [])) < len(names.get("example", [])):
        cols["example"], cols["dok"] = cols["dok"], cols["example"]
        names["example"], names["dok"] = names["dok"], names["example"]
    ex_col = cols.get("example")
    ys_row = (
        find_lines(cols["exercises"] - 25, cols["exercises"] + 25, top - 6, bottom)
        if "exercises" in cols
        else []
    )
    row_spans = list(pairwise(ys_row))
    if not row_spans:  # لا خطوط: رجوع إلى التجميع بالمسافة
        grouped: list[list[Any]] = []
        for t, b in kept:
            yc = (b[1] + b[3]) // 2
            if grouped and abs(grouped[-1][0] - yc) <= 22:
                grouped[-1][1].append((t, b))
            else:
                grouped.append([yc, [(t, b)]])
        row_spans = [(g[1][0][1][1] - 5, g[1][-1][1][3] + 5) for g in grouped]
    ex_spans = list(pairwise(find_lines(ex_col - 25, ex_col + 25, top - 6, bottom))) if ex_col else []

    def in_span(b: Box, span: tuple[int, int]) -> bool:
        return span[0] <= (b[1] + b[3]) // 2 <= span[1]

    out: list[dict[str, Any]] = []
    for span in row_spans:
        row: dict[str, str] = {}
        for name, cs in names.items():
            inside = sorted((c for c in cs if in_span(c[1], span)), key=lambda c: (c[1][1] // 12, -c[1][0]))
            if inside:
                row[name] = " ".join(t for t, _ in inside)
        yc = (span[0] + span[1]) // 2
        r: dict[str, Any] = {
            "y": yc,
            "exercises": parse_numbers(row.get("exercises", "")),
            "dok": int(row["dok"]) if row.get("dok", "").isdigit() else None,
            "standard": row.get("standard"),
        }
        if ex_col:
            ex_span = next((e for e in ex_spans if e[0] <= yc <= e[1]), None)
            label = next(
                (t for t, b in names["example"] if ex_span and in_span(b, ex_span) and t.isdigit()), None
            )
            r["example"] = int(label) if label else None
        out.append(r)
    return out


def table_pages(book: Book) -> list[int]:
    """صفحات النص التي فيها عنوان الجدول (بلا فراغ ولا علامة اتجاه)."""
    title = squash(settings(book)["title"])
    found = []
    for path in sorted(book.dir("ocr").glob("*.txt")):
        if title in squash(path.read_text(encoding="utf-8")):
            found.append(int(path.stem))
    return found


def build(
    book: Book,
    boxes_of: Callable[[int], Boxes],
    lines: Callable[..., list[int]] | None = None,
) -> dict[int, dict[str, Any]]:
    """جدول كل صفحة تحليل بصفوف فيها تمارين؛ الصفحة بلا مثال مقروء أو بلا صفوف تُهمَل. `lines` لحقن كاشف الخطوط في الاختبار."""
    cfg = settings(book)
    out: dict[int, dict[str, Any]] = {}
    for n in table_pages(book):
        boxes = boxes_of(n)
        image = book.dir("render") / f"{n:04d}.png"
        rows = parse(boxes, image, cfg, lines)
        if rows and any(r.get("example") for r in rows):
            kept = [{k: v for k, v in r.items() if k != "y"} for r in rows if r["exercises"]]
            out[n] = {"rows": kept, "task_guide": task_guide(boxes, cfg)}
    return out


def write(book: Book, result: dict[int, dict[str, Any]]) -> None:
    """يكتب ملف كل صفحة ثم الملخص (علامة اكتمال المرحلة). لا يحذف ملفًا قديمًا: صفحة سقطت من الناتج يراجعها المالك بيده."""
    folder = book.dir("tables")
    folder.mkdir(parents=True, exist_ok=True)
    for n, payload in result.items():
        (folder / f"{n:04d}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    book.output("tables").write_text(
        json.dumps(summarize(result), ensure_ascii=False, indent=1), encoding="utf-8"
    )


def summarize(result: dict[int, dict[str, Any]]) -> dict[str, Any]:
    return {
        "pages": sorted(result),
        "rows": sum(len(p["rows"]) for p in result.values()),
        "with_task_guide": sum(bool(p["task_guide"]) for p in result.values()),
    }
