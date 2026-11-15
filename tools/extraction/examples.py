"""حدود الأمثلة داخل الدرس: رقم كل مثال وصفحة بدايته ونهايته، بقواعد حتمية على نص OCR (ورؤية اختيارية تؤكد).

أرقام الأمثلة من النمط examples.pattern (مجموعة واحدة: الرقم). السقف examples.max (افتراضًا 9) وسلسلة الأرقام لا تقفز أكثر
من examples.jump (افتراضًا 2) من 1، فما فوقها رقم شارد (جدول أو تاريخ) يُرفض ويُسجَّل في rejected.
المصادر المستقلة: ocr (نص الصفحة)، label (ترقيم تسلسلي لكلمة «مثال» وحدها حين لا تُقرأ أرقام الشارات؛ examples.numbering: sequence)، vision (رؤية الصفحة كاملة، dirs.vision)، badge (شارات مقتصّة، dirs.badges). إن وُجدت شارات
فهي المرجع للمجموعة وللصفحة الأولى، وما سواها يُرفض. بلا شارات تكون الصفحة الأولى أول ظهور للرقم، والمثال ok إن شهد له
مصدران على الأقل، وإلا review. ونهاية المثال الصفحة التي قبل بداية التالي (أو نفسها إن تشاركا صفحة)، وآخر مثال ينتهي
عند أول صفحة تمارين (markers.exercises) أو نهاية الدرس، وعلامته end_estimated.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from .config import Book
from .fields import field
from .text import chain_max, norm

DEFAULT_PATTERN = r"(?<![ء-ي])مثال\s*([0-9]+)(?![0-9.])"
DEFAULTS = {"max": 9, "jump": 2}


def settings(book: Book) -> dict[str, Any]:
    return {**DEFAULTS, **book.get("examples", {})}


def numbers_in(text: str, pattern: str = DEFAULT_PATTERN, ceiling: int = 9) -> set[int]:
    return {int(x) for x in re.findall(pattern, norm(text)) if 1 <= int(x) <= ceiling}


def _json(path: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def vision_numbers(book: Book, page: int, ceiling: int = 9) -> set[int]:
    """أرقام أمثلة الصفحة من رؤية الصفحة كاملة (dirs.vision/NNNN.json بمفتاح examples) إن وُجد؛ مصدر مستقل عن OCR."""
    if not book.has_dir("vision"):
        return set()
    data = _json(book.dir("vision") / f"{page:04d}.json") or {}
    return {int(x) for x in data.get("examples", []) if isinstance(x, int) and 1 <= x <= ceiling}


def badge_numbers(book: Book, page: int, ceiling: int = 9) -> set[int]:
    """أرقام شارات الأمثلة المقتصّة بالرؤية (dirs.badges/NNNN.json قائمة كائنات بمفتاح n): أدق مصدر، فإن وُجد فهو المرجع."""
    if not book.has_dir("badges"):
        return set()
    data = _json(book.dir("badges") / f"{page:04d}.json") or []
    return {
        int(e["n"])
        for e in data
        if isinstance(e, dict) and isinstance(e.get("n"), int) and 1 <= e["n"] <= ceiling
    }


Source = Callable[[int], set[int]]
LABEL_LINE = r"^\s*مثال\s*\S?\s*$"


def label_sequence(texts: dict[int, str], pattern: str = LABEL_LINE) -> dict[int, set[int]]:
    """ترقيم بالتسلسل حيث لا يقرأ OCR رقم الشارة (دائرة ملونة): كل سطر يحوي كلمة «مثال» وحدها (مع رمز شارد أقصاه واحد)
    هو مثال جديد، يُرقَّم بترتيب ظهوره في صفحات الدرس. تقدير مشتق: يخطئ إن فاتت OCR كلمة أو كُرِّرت."""
    rx = re.compile(pattern, re.MULTILINE)
    out: dict[int, set[int]] = {}
    count = 0
    for page in sorted(texts):
        hits = len(rx.findall(norm(texts[page])))
        if hits:
            out[page] = set(range(count + 1, count + hits + 1))
            count += hits
    return out


def lesson_boundaries(
    span: tuple[int, int], sources: dict[str, Source], exercises_page: int | None, jump: int
) -> dict[str, Any]:
    """sources: اسم المصدر (ocr وvision وbadge) -> دالة صفحة ترجع أرقام أمثلتها. إن وُجدت شارات فهي المرجع وما سواها مرفوض."""
    first, last = span
    per_page = {n: {name: fn(n) for name, fn in sources.items()} for n in range(first, last + 1)}
    seen: dict[int, set[str]] = {}
    for hits in per_page.values():
        for name, nums in hits.items():
            for x in nums:
                seen.setdefault(x, set()).add(name)
    authoritative = "badge" if any("badge" in names for names in seen.values()) else None
    pool = {x for x, names in seen.items() if not authoritative or authoritative in names}
    limit = chain_max(pool, jump)
    accepted = sorted(x for x in pool if x <= limit)
    rejected = sorted(set(seen) - set(accepted))
    starts = {
        x: next(
            n
            for n, hits in per_page.items()
            if any(x in nums for name, nums in hits.items() if not authoritative or name == authoritative)
        )
        for x in accepted
    }
    stop = min(exercises_page - 1, last) if exercises_page and first <= exercises_page <= last + 1 else last
    out = []
    for i, x in enumerate(accepted):
        nxt = starts[accepted[i + 1]] if i + 1 < len(accepted) else None
        end = (nxt if nxt == starts[x] else nxt - 1) if nxt else max(stop, starts[x])
        names = sorted(seen[x])
        out.append(
            {
                "n": x,
                "start": starts[x],
                "end": end,
                "end_estimated": nxt is None,
                "evidence": names,
                # شاهد واحد غير الشارة (OCR وحده أو الرؤية وحدها) لا يكفي لـ ok
                "status": "ok" if "badge" in names or len(names) >= 2 else "review",
            }
        )
    monotone = all(a["start"] <= b["start"] for a, b in zip(out, out[1:], strict=False))
    return {
        "examples": out,
        "rejected": rejected,
        "monotone": monotone,
        "contiguous": [e["n"] for e in out] == list(range(1, len(out) + 1)),
        "authoritative": authoritative,
    }


def exercises_start(book: Book, span: tuple[int, int], pages: dict[int, str]) -> int | None:
    marker = book["markers"].get("exercises")
    if not marker:
        return None
    from .text import squash

    m = squash(marker)
    return next((n for n in range(span[0], span[1] + 1) if m in pages.get(n, "")), None)


def build(book: Book, layout: dict[str, Any], pages_squashed: dict[int, str]) -> dict[str, Any]:
    cfg = settings(book)
    pattern = cfg.get("pattern", DEFAULT_PATTERN)
    result: dict[str, Any] = {"book": book.id, "lessons": {}}
    for r in layout["lessons"]:
        if not r["pages_pdf"]:
            result["lessons"][r["id"]] = field([], "derived", "missing")
            continue
        span = (r["pages_pdf"][0], r["pages_pdf"][1])
        sources: dict[str, Source] = {"ocr": lambda n: numbers_in(book.page_text(n), pattern, cfg["max"])}
        if cfg.get("numbering") == "sequence":
            seq = label_sequence(
                {n: book.page_text(n) for n in range(span[0], span[1] + 1)},
                cfg.get("label_pattern", LABEL_LINE),
            )
            sources["label"] = lambda n, s=seq: {x for x in s.get(n, set()) if x <= cfg["max"]}
        if book.has_dir("vision"):
            sources["vision"] = lambda n: vision_numbers(book, n, cfg["max"])
        if book.has_dir("badges"):
            sources["badge"] = lambda n: badge_numbers(book, n, cfg["max"])
        got = lesson_boundaries(span, sources, exercises_start(book, span, pages_squashed), cfg["jump"])
        ok = (
            got["examples"]
            and got["monotone"]
            and got["contiguous"]
            and not got["rejected"]
            and all(e["status"] == "ok" for e in got["examples"])
        )
        status = "missing" if not got["examples"] else ("ok" if ok else "review")
        result["lessons"][r["id"]] = field(
            got["examples"],
            "derived",
            status,
            rejected=got["rejected"],
            monotone=got["monotone"],
            contiguous=got["contiguous"],
            authoritative=got["authoritative"],
        )
    return result


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    ls = result["lessons"]
    return {
        "lessons": len(ls),
        "examples": sum(len(v["value"]) for v in ls.values()),
        "ok": sum(v["status"] == "ok" for v in ls.values()),
        "review": [k for k, v in ls.items() if v["status"] == "review"],
        "missing": [k for k, v in ls.items() if v["status"] == "missing"],
    }
