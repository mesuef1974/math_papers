"""مفردات الدرس (فقرتا «مراجعة المصطلحات» و«المصطلحات الجديدة») من صفحة افتتاحيته: جانب الدمج بلا نموذج لغة.

المصدران: قراءة رؤية لبطاقة المصطلحات محفوظة في dirs.vocab/NNNN.json (مفاتيح review وnew وflat؛ أزواج ar/en)، وOCR مرجعًا مستقلًّا
يتحقق من حضور العربي وموضعه بين العنوانين. الدمج: kind من الرؤية، وstatus=ok حين يحضر العربي في OCR والإنجليزي قريب (نسبة تشابه)
والفقرة موافقة لموضعه، وإلا review. هجاء ما تكرر في الذهبيات (dirs.gold/lesson_*.json، مفتاح vocabulary) يُصحَّح بها.
الإعداد `vocabulary` اختياري: review_head وnew_head (كلمة واحدة موحّدة) وen_match وsnap. تشغيل الرؤية نفسه خارج هذه الوحدة.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

from .config import Book
from .text import norm

DEFAULTS = {"review_head": "مراجعه", "new_head": "الجديده", "en_match": 0.8, "snap": 0.85}


def settings(book: Book) -> dict[str, Any]:
    return {**DEFAULTS, **book.get("vocabulary", {})}


def squash(text: str) -> str:
    return re.sub(r"[^\w]", "", norm(text)).replace("_", "")


def en_key(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def section_of(lines: list[str], ar: str, en: str, cfg: dict[str, Any]) -> tuple[bool, str | None, bool]:
    """(العربي حاضر في OCR، الفقرة بحسب موضعه بين العنوانين، الإنجليزي قريب من سطر OCR)."""
    flat = [squash(x) for x in lines]
    review_at, new_at = headings(lines, cfg)
    key = squash(ar)
    at = next((i for i, x in enumerate(flat) if key and key in x), None)
    section = None
    if at is not None and review_at is not None and new_at is not None:
        in_review = review_at < at < new_at or (new_at < review_at and at > review_at)
        section = "review" if in_review else "new"
    ek = en_key(en)
    near = any(
        SequenceMatcher(None, ek, en_key(x)).ratio() >= cfg["en_match"] or (ek and ek in en_key(x))
        for x in lines
        if len(en_key(x)) >= 3
    ) or any(
        ek and SequenceMatcher(None, ek, en_key(" ".join(lines[i : i + 2]))).ratio() >= cfg["en_match"]
        for i in range(len(lines))
    )
    return at is not None, section, near


def headings(lines: list[str], cfg: dict[str, Any]) -> tuple[int | None, int | None]:
    def find(head: str) -> int | None:
        return next((i for i, x in enumerate(lines) if squash(head) in squash(x)), None)

    return find(cfg["review_head"]), find(cfg["new_head"])


def glossary(book: Book) -> list[dict[str, str]]:
    """مصطلحات الذهبيات: مرجع تصحيح هجاء الرؤية لا مصدر مصطلحات جديدة."""
    if not book.has_dir("gold"):
        return []
    out: dict[str, dict[str, str]] = {}
    for path in sorted(book.dir("gold").glob("lesson_*.json")):
        for v in json.loads(path.read_text(encoding="utf-8")).get("vocabulary", []):
            out.setdefault(squash(v["ar"]), {"ar": v["ar"], "en": v["en"]})
    return list(out.values())


def snap(ar: str, en: str, gloss: list[dict[str, str]], threshold: float) -> dict[str, str] | None:
    for g in gloss:
        if (
            SequenceMatcher(None, squash(ar), squash(g["ar"])).ratio() >= threshold
            and SequenceMatcher(None, en_key(en), en_key(g["en"])).ratio() >= threshold
        ):
            return g
    return None


def terms(book: Book, page: int, fix_spelling: bool = True) -> list[dict[str, Any]]:
    """مصطلحات صفحة افتتاحية؛ فارغة إن لم تُقرأ بالرؤية."""
    if not book.has_dir("vocab"):
        return []
    path = book.dir("vocab") / f"{page:04d}.json"
    if not path.exists():
        return []
    cfg = settings(book)
    vision = json.loads(path.read_text(encoding="utf-8"))
    lines = norm(book.page_text(page)).split("\n")
    review_at, new_at = headings(lines, cfg)
    only = (
        "review"
        if new_at is None and review_at is not None
        else "new"
        if review_at is None and new_at is not None
        else None
    )
    cands = (
        [("review", t) for t in vision["review"]]
        + [("new", t) for t in vision["new"]]
        + [(None, t) for t in vision.get("flat", [])]
    )
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    gloss = glossary(book) if fix_spelling else []
    for kind, t in cands:
        ar, en = t["ar"].strip(), t["en"].strip()
        if not ar or not en or "المصطلحات" in ar or squash(ar) in seen:  # عنوان فقرة أو مكرَّر
            continue
        seen.add(squash(ar))
        known = snap(ar, en, gloss, cfg["snap"])
        if known:  # الأزواج المصحَّحة بالمرجع الذهبي لا تحتاج مطابقة OCR الضجيجية
            ar, en = known["ar"], known["en"]
        present, section, near = section_of(lines, ar, en, cfg)
        near = near or bool(known)
        present = present or bool(known)
        # فقرة واحدة ظاهرة في OCR فكل المصطلحات منها (الرؤية قد تضعها في الأخرى)
        final = only or kind or section or "review"
        agrees = only is not None or kind is None or section in (None, kind) or bool(known)
        ok = present and near and agrees and bool(kind or only or section)
        rows.append({"ar": ar, "en": en, "kind": final, "status": "ok" if ok else "review"})
    return rows
