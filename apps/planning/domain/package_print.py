"""لقطة بند من باقة الحصة كما تُطبع: JSON يحفظه `AssignmentItem` فلا يغيّره تعديل المولّدات بعد التسليم. نقي."""

from __future__ import annotations

from apps.papers.domain.generators import Problem
from apps.papers.domain.item_bank import Item

from .lesson_package import BookEntry, Entry, GeneratedEntry

BOOK, GENERATED, ITEM = "book", "generated", "item"


def _question(source: Problem | Item) -> dict:
    return {"stem": source.stem, "graph": source.graph, "steps": list(source.steps)}


def entry_snapshot(entry: Entry) -> dict:
    """حقول البند كلها: تمرين الكتاب برقمه وصفحته وحدهما، والمولَّد وبند التحضير بنصه وإجابته."""
    if isinstance(entry, BookEntry):
        return {
            "source": BOOK,
            "example": entry.example,
            "dok": entry.dok,
            "number": entry.number,
            "page": entry.page,
        }
    if isinstance(entry, GeneratedEntry):
        return {
            "source": GENERATED,
            "example": entry.example,
            "variant": entry.variant,
            "seed": entry.seed,
            "answer": entry.problem.answer,
            **_question(entry.problem),
        }
    item = entry.item
    return {
        "source": ITEM,
        "example": item.example,
        "variant": item.variant,
        "options": [o.text for o in item.options],
        "answer_index": item.answer_index,
        **_question(item),
    }
