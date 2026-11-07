"""تجميع الأوراق. لا كتابة في قاعدة البيانات: البذرة نفسها تعطي الورقة نفسها دائمًا."""

from __future__ import annotations

import random
import secrets
from collections import defaultdict
from dataclasses import dataclass

from apps.curriculum import selectors
from apps.curriculum.models import BlueprintItem

from .domain.generators import Problem, available_lessons, generate

MAX_SEED = 2**31 - 1
PART_LABELS = "ABCDEFGH"


class UnknownBlueprintError(LookupError):
    pass


class UnknownLessonError(LookupError):
    pass


@dataclass(frozen=True)
class PartSlot:
    label: str
    lesson: str
    lesson_title: str
    kind: str
    marks: int


def new_seed() -> int:
    return secrets.randbelow(MAX_SEED)


def render_part(problem: Problem, slot: PartSlot, rng: random.Random) -> dict:
    options: list[str] = []
    if slot.kind == BlueprintItem.Kind.MCQ:
        options = [problem.answer, *problem.wrong]
        rng.shuffle(options)
    return {
        "label": slot.label,
        "lesson": slot.lesson,
        "lesson_title": slot.lesson_title,
        "marks": slot.marks,
        "level": problem.level,
        "stem": problem.stem,
        "options": options,
        "answer": problem.answer,
        "steps": list(problem.steps),
    }


def build_exam(slug: str, seed: int | None = None) -> dict:
    blueprint = selectors.blueprint_with_items(slug)
    if blueprint is None:
        raise UnknownBlueprintError(slug)
    seed = new_seed() if seed is None else seed
    rng = random.Random(seed)  # noqa: S311 — بذرة قابلة للإعادة، لا استعمال أمني
    grouped: dict[int, list[BlueprintItem]] = defaultdict(list)
    for item in blueprint.items.all():
        grouped[item.question_number].append(item)

    used: set[str] = set()
    questions = []
    level_marks: dict[str, int] = defaultdict(int)
    for number, items in sorted(grouped.items()):
        parts = []
        for position, item in enumerate(items):
            label = PART_LABELS[position] if len(items) > 1 else ""
            slot = PartSlot(label, item.lesson.code, item.lesson.title, item.kind, item.marks)
            problem = generate(item.lesson.code, rng, item.kind, used)
            used.add(problem.stem)
            level_marks[problem.level] += item.marks
            parts.append(render_part(problem, slot, rng))
        questions.append(
            {"number": number, "kind": items[0].kind, "marks": sum(i.marks for i in items), "parts": parts}
        )
    return {
        "title": blueprint.title,
        "seed": seed,
        "total_marks": blueprint.total_marks,
        "is_forecast": blueprint.is_forecast,
        "level_marks": dict(level_marks),
        "questions": questions,
    }


def build_worksheet(lesson_code: str, count: int, seed: int | None = None) -> dict:
    lesson = selectors.lessons().filter(code=lesson_code).first()
    if lesson is None or lesson_code not in available_lessons():
        raise UnknownLessonError(lesson_code)
    seed = new_seed() if seed is None else seed
    rng = random.Random(seed)  # noqa: S311 — بذرة قابلة للإعادة، لا استعمال أمني
    used: set[str] = set()
    questions = []
    for number in range(1, count + 1):
        problem = generate(lesson.code, rng, BlueprintItem.Kind.ESSAY, used)
        used.add(problem.stem)
        slot = PartSlot("", lesson.code, lesson.title, BlueprintItem.Kind.ESSAY, 0)
        questions.append(
            {"number": number, "kind": slot.kind, "marks": 0, "parts": [render_part(problem, slot, rng)]}
        )
    return {
        "title": f"ورقة عمل: {lesson.title}",
        "seed": seed,
        "total_marks": 0,
        "is_forecast": False,
        "level_marks": {},
        "questions": questions,
    }
