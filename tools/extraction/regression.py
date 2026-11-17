"""انحدار سجل الدرس على المعيار الذهبي (dirs.gold): يقيس ولا يدخل الحقول.

الذهبي المكتمل `lesson_X_Y.json` (استُخرج بصريًا وراجعه المالك) يقابل كل حقل في السجل؛ ولدرس بلا ذهبي كامل تُقارَن صفحة اختباره
بـ `quiz_visual.json` إن وُجد. تمثيلات الأمثلة حكم بشري فتُقاس (دقة واسترجاع) في `soft` ولا تُشترط في النجاح.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

from . import vocabulary
from .config import Book
from .text import dashes, norm, parse_numbers

REPS = ("جدول", "بياني", "جبري", "سياق")
VOCAB_RATIO = 0.85


def _gold(book: Book, tag: str) -> dict[str, Any] | None:
    if not book.has_dir("gold"):
        return None
    path = book.dir("gold") / f"lesson_{tag}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _codes(book: Book, value: Any) -> set[str]:
    pattern = f"(?:{book['standards']['pattern']})"
    text = json.dumps(value, ensure_ascii=False)
    return {re.sub(r"\s+", "", c).upper() for c in re.findall(pattern, text, re.IGNORECASE)}


def visual(book: Book, lesson: dict[str, Any]) -> dict[str, bool] | None:
    """انحدار على القراءة البصرية لصفحة الاختبار (gold/quiz_visual.json) لدرس بلا ذهبي كامل."""
    if not book.has_dir("gold"):
        return None
    path = book.dir("gold") / "quiz_visual.json"
    if not path.exists():
        return None
    ref = json.loads(path.read_text(encoding="utf-8")).get(lesson["id"])
    if ref is None:
        return None
    quiz = lesson["lesson_quiz"]["value"]
    return {
        "quiz_questions": ref["questions"] == quiz["questions"],
        "quiz_depths": ref["depth"] == quiz["depth"],
        "quiz_standards_union": {ref["standard"]}
        == {c for cs in quiz["standards_by_question"].values() for c in cs},
        "quiz_status_ok": lesson["lesson_quiz"]["status"] == "ok",
    }


def _expand(ranges: set[str]) -> set[int]:
    nums: set[int] = set()
    for r in ranges:
        m = re.match(r"^(\d+)-(\d+)$", r)
        nums |= set(range(int(m[1]), int(m[2]) + 1)) if m else {int(x) for x in re.findall(r"\d+", r)}
    return nums


def _words(text: Any) -> list[str]:
    return dashes(norm(str(text))).split()


def vs_gold(book: Book, lesson: dict[str, Any], tag: str) -> dict[str, bool] | None:
    gold = _gold(book, tag)
    if gold is None:
        return visual(book, lesson)
    gold_rows: dict[tuple[Any, Any], set[int]] = {}
    for r in gold["exercise_analysis"]:
        gold_rows.setdefault((r["example"], r["depth"]), set()).update(parse_numbers(r["exercises"]))
    mine = {(r["example"], r["dok"]): set(r["exercises"]) for r in lesson["exercise_analysis"]["value"]}
    tg = lesson["task_guide"]["value"] or {}
    gq = gold["lesson_quiz"]
    gold_std = _codes(book, gq.get("standard", ""))
    quiz = lesson["lesson_quiz"]["value"]
    gv = gold.get("vocabulary", [])
    raw = vocabulary.terms(book, lesson["pages"]["opener"]["value"], fix_spelling=False)
    return {
        "vocabulary": len(raw) == len(gv)
        and all(
            a["kind"] == b["kind"]
            and SequenceMatcher(None, vocabulary.squash(a["ar"]), vocabulary.squash(b["ar"])).ratio()
            >= VOCAB_RATIO
            and SequenceMatcher(None, vocabulary.en_key(a["en"]), vocabulary.en_key(b["en"])).ratio()
            >= VOCAB_RATIO
            for a, b in zip(raw, gv, strict=True)
        ),
        "span": gold["pages_pdf"] == lesson["pages"]["span_pdf"]["value"],
        "examples": {e["n"] for e in gold["examples"]} == {e["n"] for e in lesson["examples"]},
        "example_pages": {e["n"]: e["page_pdf"] for e in gold["examples"]}
        == {e["n"]: e["page_pdf"]["value"] for e in lesson["examples"]},
        "example_titles_present": all(e["skill"]["value"] for e in lesson["examples"]),
        "exercises": _expand({re.sub(r"\s+", "", s["range"]) for s in gold["exercise_sections"]})
        == set(lesson["exercises"]["value"]),
        "total_exercises": gold.get("total_exercises") == lesson["exercises"]["total"],
        "practices": set(gold["practices"]) == set(lesson["practices"]["value"]),
        "exercise_analysis": mine == gold_rows,
        "task_guide": all(
            _words(tg.get(k, "")) == _words(gold["task_guide"][k]) for k in ("basic", "advanced")
        ),
        "quiz_standards": _codes(book, gq.get("standard", "")) == set(lesson["standards"]["value"]),
        "quiz_questions": gq.get("questions") == quiz["questions"],
        "quiz_depths": gq.get("depth") == quiz["depth"],
        "quiz_standards_union": gold_std == {c for cs in quiz["standards_by_question"].values() for c in cs},
    }


def soft(book: Book, lesson: dict[str, Any], tag: str) -> dict[str, Any] | None:
    """تمثيلات الأمثلة مقابل الذهبي: حكم بشري لا يُشترط فيه التطابق التام، فيُقاس ولا يدخل نجاح الانحدار."""
    gold_lesson = _gold(book, tag)
    if gold_lesson is None:
        return None
    gold = {e["n"]: {k for k in REPS if k in e["representation"]} for e in gold_lesson["examples"]}
    tp = fp = fn = exact = 0
    for e in lesson["examples"]:
        mine = {"سياق" if x == "سياق حياتي" else x for x in (e["representation"]["value"] or [])}
        ref = gold.get(e["n"], set())
        tp, fp, fn = tp + len(ref & mine), fp + len(mine - ref), fn + len(ref - mine)
        exact += ref == mine
    return {
        "representation_exact": exact,
        "of": len(gold),
        "precision": round(tp / (tp + fp), 2) if tp + fp else None,
        "recall": round(tp / (tp + fn), 2) if tp + fn else None,
    }
