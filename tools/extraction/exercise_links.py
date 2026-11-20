"""ربط تدريبات الكتاب بالأمثلة لكتاب بلا جدول «تحليل التمارين»: استنتاج من تجاور الأرقام في الصفحة، يراجعه المالك.

المصدران: `examples.json` (أمثلة الدرس المقبولة وصفحاتها) ورؤية الصفحة `dirs.vision/NNNN.json` (`examples` و`exercises`).
القاعدة: كل صفحة من صفحات الدرس فيها أرقام تدريبات تُربط تدريباتها بكل مثال مقبول يظهر رقمه في الصفحة نفسها (صفحة المثال
نفسه، أو صفحة تمارين تحيل إليه). تدريبات صفحة بلا رقم مثال تبقى في `unlinked`، والصفحة التي فيها أكثر من مثال تُسجَّل في
`shared_pages` لأن تدريباتها نُسبت إليها كلها. أرقام التدريبات سلسلة من 1 بسقف `exercises.max` وقفزة `exercises.jump` (كالدمج)،
وقائمة رؤية أطول من `fusion.degenerate` في صفحة تُسقَط كلها. حالة كل درس `review` دائمًا (أو `missing` بلا أمثلة أو بلا ربط):
الربط مستنتج لا مقروء، ولا يصير `ok` إلا بتصحيح من المالك في `corrections.yaml`.
الدرس الذي في `exercise_badges.json` له شارة مقروءة واحدة فأكثر تؤخذ صفوفه من الشارات (`method: badges`): كل تدريب لمثال شارته
لا لكل أمثلة الصفحة؛ وغيره يبقى على التجاور (`method: adjacency`).
"""

from __future__ import annotations

import json
from typing import Any

from .config import Book
from .exercise_badges import readable
from .fields import field
from .fusion import settings as fusion_settings
from .text import chain_max


def page_numbers(book: Book, page: int) -> tuple[set[int], set[int]]:
    """(أرقام الأمثلة، أرقام التدريبات) كما رأتها الرؤية في الصفحة؛ فارغتان بلا ملف."""
    path = book.dir("vision") / f"{page:04d}.json"
    if not path.exists():
        return set(), set()
    data = json.loads(path.read_text(encoding="utf-8"))

    def ints(key: str) -> set[int]:
        return {x for x in data.get(key, []) if isinstance(x, int) and not isinstance(x, bool) and x >= 1}

    return ints("examples"), ints("exercises")


def link(
    span: tuple[int, int],
    accepted: set[int],
    pages: dict[int, tuple[set[int], set[int]]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """ربط درس واحد. `pages`: صفحة → (أمثلة، تدريبات) من الرؤية؛ `cfg` فيه max_exercise وjump.exercises وdegenerate."""
    first, last = span
    seen = {
        n: {x for x in pages.get(n, (set(), set()))[1] if x <= cfg["max_exercise"]}
        for n in range(first, last + 1)
    }
    seen = {n: (set() if len(xs) > cfg["degenerate"] else xs) for n, xs in seen.items()}
    cap = chain_max(set().union(*seen.values()), cfg["jump"]["exercises"])
    linked: dict[int, set[int]] = {x: set() for x in accepted}
    where: dict[int, set[int]] = {x: set() for x in accepted}
    unlinked: set[int] = set()
    shared: list[int] = []
    for n, exercises in seen.items():
        exercises = {x for x in exercises if x <= cap}
        if not exercises:
            continue
        here = pages[n][0] & accepted
        if not here:
            unlinked |= exercises
            continue
        if len(here) > 1:
            shared.append(n)
        for example in here:
            linked[example] |= exercises
            where[example].add(n)
    everything = set().union(*linked.values()) if linked else set()
    return {
        "links": [
            {"example": x, "exercises": sorted(linked[x]), "pages": sorted(where[x])}
            for x in sorted(accepted)
        ],
        "unlinked": sorted(unlinked - everything),
        "shared_pages": shared,
    }


def badge_lessons(book: Book) -> dict[str, Any]:
    """دروس `exercise_badges.json` إن كُتب (مرحلة الشارات تُشغَّل قبل هذه بالاسم)؛ فارغة بلا ملف."""
    path = book.output("exercise_badges")
    return json.loads(path.read_text(encoding="utf-8"))["lessons"] if path.exists() else {}


def build(book: Book, layout: dict[str, Any], examples: dict[str, Any]) -> dict[str, Any]:
    cfg = fusion_settings(book)
    badges = badge_lessons(book)
    result: dict[str, Any] = {"book": book.id, "lessons": {}}
    for r in layout["lessons"]:
        known = examples["lessons"].get(r["id"], {}).get("value") or []
        accepted = {e["n"] for e in known}
        seen = badges.get(r["id"])
        if r["pages_pdf"] and accepted and readable(seen):
            # شارة مقروءة واحدة تكفي: إحالة الصفحة نفسها تغلب تجاور الأرقام
            result["lessons"][r["id"]] = field(
                seen["value"],
                "derived",
                "review" if any(row["exercises"] for row in seen["value"]) else "missing",
                unlinked=seen["unlinked"],
                shared_pages=[],
                method="badges",
            )
            continue
        if not r["pages_pdf"] or not accepted or not book.has_dir("vision"):
            result["lessons"][r["id"]] = field([], "derived", "missing", method="adjacency")
            continue
        span = (r["pages_pdf"][0], r["pages_pdf"][1])
        pages = {n: page_numbers(book, n) for n in range(span[0], span[1] + 1)}
        got = link(span, accepted, pages, cfg)
        status = "review" if any(row["exercises"] for row in got["links"]) else "missing"
        result["lessons"][r["id"]] = field(
            got["links"],
            "derived",
            status,
            unlinked=got["unlinked"],
            shared_pages=got["shared_pages"],
            method="adjacency",
        )
    return result


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    ls = result["lessons"]
    rows = [row for v in ls.values() for row in v["value"]]
    return {
        "lessons": len(ls),
        "examples": len(rows),
        "linked_examples": sum(bool(row["exercises"]) for row in rows),
        "review": [k for k, v in ls.items() if v["status"] == "review"],
        "missing": [k for k, v in ls.items() if v["status"] == "missing"],
    }
