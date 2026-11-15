"""أهداف كل درس من افتتاحيته بلا نموذج لغة، وفعل كل هدف ومستواه ببلوم بمعجم bloom_lexicon_ar.json.

الاستخراج هندسي من صناديق OCR: صناديق العمود بين markers.objective_intro وأول markers.objective_end، وتبدأ فقرة هدف عند كل علامة
(كشف لوني بالصورة إن أُعدّ objectives.check في book.yaml) وإلا بالفاصل الرأسي `gap` والمعجم، وحالة ذلك review.
الفعل غير الموجود في المعجم unclassified ولا يُخمَّن. كل هدف بمصدر نصه (guide) ومصدر مستواه (derived) وحالته.
الاعتماد على الصورة (numpy وPillow) كسول: غيابه يعطل كشف العلامات وحده.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from .config import LEXICON, Book
from .fields import field
from .text import norm, strip_al

ARABIC = re.compile(r"[ء-ي]")
DEFAULTS = {"column": "right", "gap": 14, "noise_chars": 3, "max_region": 330, "min_confidence": 0.8}
Box = list[int]
Items = list[tuple[str, Box]]


def settings(book: Book) -> dict[str, Any]:
    return {**DEFAULTS, **book.get("objectives", {})}


def lexicon() -> tuple[str, dict[str, tuple[str, float]]]:
    raw = json.loads(LEXICON.read_text(encoding="utf-8"))
    return raw["version"], {strip_al(norm(k)): (v[0], v[1]) for k, v in raw["entries"].items()}


def classify(text: str, lex: dict[str, tuple[str, float]]) -> tuple[str, str, float | None]:
    """(الفعل، مستوى بلوم، الثقة) من أول كلمة؛ خارج المعجم -> unclassified بلا ثقة."""
    words = norm(text).split()
    verb = strip_al(words[0]) if words else ""
    bloom, conf = lex.get(verb, ("unclassified", None))
    return verb, bloom, conf


def checkmarks(image_path: Any, cfg: dict[str, Any], y_from: int, y_to: float) -> list[int]:
    """مراكز علامات الأهداف الملونة في عمودها بين y_from وy_to، بمعالجة الصورة (objectives.check: x نسبة، rgb، tol)."""
    import numpy as np
    from PIL import Image

    chk = cfg.get("check")
    if not chk:
        return []
    img = np.asarray(Image.open(image_path).convert("RGB")).astype(int)
    w = img.shape[1]
    lo, hi = int(w * chk["x"][0]), int(w * chk["x"][1])
    top, bottom = max(0, y_from), min(img.shape[0], int(y_to))
    sub = img[top:bottom, lo:hi]
    mask = (np.abs(sub - np.array(chk["rgb"])) < chk.get("tol", 40)).all(axis=2)
    rows = np.nonzero(mask.sum(axis=1) > 2)[0] + top
    runs: list[list[int]] = []
    for r in rows:
        if runs and r <= runs[-1][1] + 3:
            runs[-1][1] = int(r)
        else:
            runs.append([int(r), int(r)])
    return [(a + z) // 2 for a, z in runs if z - a >= 8]


def segment(
    items: Items,
    book: Book,
    lex: dict[str, tuple[str, float]],
    marks: Callable[[int, float], list[int]] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """أهداف صفحة افتتاح وطريقة التجزئة: check (بعلامات) أو gap (احتياطي يلزمه review) أو none (لا مقدمة أهداف)."""
    cfg = settings(book)
    m = book["markers"]
    intro, ends = norm(m["objective_intro"]), [norm(e) for e in m["objective_end"]]
    squash_in = lambda t: re.sub(r"\s+", "", t)  # noqa: E731
    normed = [(norm(t).strip(), b) for t, b in items]
    start = next((b for t, b in normed if squash_in(intro) in squash_in(t)), None)
    if start is None:
        return [], "none"
    page_w = max(b[2] for _, b in normed)
    if cfg["column"] == "right":
        col = [(t, b) for t, b in normed if b[0] > page_w / 2 - 1 and b[1] >= start[3] - 4]
    elif cfg["column"] == "left":
        col = [(t, b) for t, b in normed if b[2] <= page_w / 2 + 1 and b[1] >= start[3] - 4]
    else:
        col = [(t, b) for t, b in normed if b[1] >= start[3] - 4]
    col.sort(key=lambda x: x[1][1])
    end_y = next((b[1] for t, b in col if any(squash_in(e) in squash_in(t) for e in ends)), float("inf"))
    label = squash_in(norm(m["objective_label"]))
    lines = [
        (t, b)
        for t, b in col
        if b[1] < end_y
        and len(t.replace(" ", "")) > cfg["noise_chars"]
        and ARABIC.search(t)
        and squash_in(t) != label
        and squash_in(intro) not in squash_in(t)
    ]
    checks = (
        marks(start[3] - 4, end_y if end_y != float("inf") else start[3] + cfg["max_region"]) if marks else []
    )
    out: list[dict[str, Any]] = []
    prev: Box | None = None
    for t, b in lines:
        t = re.sub(r"\s+", " ", t)
        if checks:
            idx = sum(1 for c in checks if c <= (b[1] + b[3]) / 2 + 5)
            new = idx > len(out) or (idx == 0 and not out)
        else:
            new = prev is None or b[1] - prev[3] >= cfg["gap"] or strip_al(t.split()[0]) in lex
        if new:
            out.append({"text": t, "lines": 1})
        else:
            out[-1]["text"] += " " + t
            out[-1]["lines"] += 1
        prev = b
    return out, "check" if checks else "gap"


def build(
    book: Book,
    layout: dict[str, Any],
    boxes_of: Callable[[int], Items],
    marks_of: Callable[[int, int, float], list[int]] | None = None,
) -> dict[str, Any]:
    """نتيجة كل الدروس. boxes_of(صفحة) يعيد الصناديق، وmarks_of(صفحة، y0، y1) مراكز العلامات (اختياري)."""
    version, lex = lexicon()
    min_conf = settings(book)["min_confidence"]
    result: dict[str, Any] = {"book": book.id, "lexicon_version": version, "lessons": {}}
    for r in layout["lessons"]:
        if not r["opener"]:
            result["lessons"][r["id"]] = field([], "guide", "missing")
            continue
        page = r["opener"]
        found, method = segment(
            boxes_of(page), book, lex, (lambda a, z, p=page: marks_of(p, a, z)) if marks_of else None
        )
        items = []
        for o in found:
            verb, bloom, conf = classify(o["text"], lex)
            ok = bloom != "unclassified" and conf is not None and conf >= min_conf and method == "check"
            items.append(
                {
                    "text": o["text"],
                    "verb": verb,
                    "bloom": bloom,
                    "confidence": conf,
                    "source": {"text": "guide", "bloom": "derived"},
                    "split": method,
                    "status": "ok" if ok else "review",
                }
            )
        status = "missing" if not items else ("ok" if all(i["status"] == "ok" for i in items) else "review")
        result["lessons"][r["id"]] = field(items, "guide", status, split=method)
    return result


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    items = [i for v in result["lessons"].values() for i in v["value"]]
    return {
        "lessons": len(result["lessons"]),
        "objectives": len(items),
        "classified": sum(i["bloom"] != "unclassified" for i in items),
        "unclassified": sum(i["bloom"] == "unclassified" for i in items),
        "review": sum(i["status"] == "review" for i in items),
        "missing_lessons": [k for k, v in result["lessons"].items() if v["status"] == "missing"],
    }
