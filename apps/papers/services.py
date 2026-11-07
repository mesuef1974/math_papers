"""تجميع الأوراق. لا كتابة في قاعدة البيانات: البذرة نفسها تعطي الورقة نفسها دائمًا."""

from __future__ import annotations

import random
import secrets
from collections import defaultdict
from dataclasses import dataclass

from apps.curriculum import selectors
from apps.curriculum.models import BlueprintItem

from .domain.generators import LEVEL_NAMES, LevelUnavailableError, Problem, available_lessons, generate

MAX_SEED = 2**31 - 1
PART_LABELS = "ABCDEFGH"
OPTION_LABELS = "أبجد"  # تطابق ترتيب عرض الخيارات في الواجهة


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
    option_graphs: list[dict] = []
    answer = problem.answer
    if problem.option_graphs:
        # خيارات رسوم: يُخلط الترتيب، والجواب اسم الخيار الصحيح بعد الخلط.
        order = list(range(len(problem.option_graphs)))
        rng.shuffle(order)
        option_graphs = [problem.option_graphs[i] for i in order]
        options = ["" for _ in order]
        answer = f"الخيار ({OPTION_LABELS[order.index(0)]})"
    elif slot.kind == BlueprintItem.Kind.MCQ:
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
        "answer": answer,
        "steps": list(problem.steps),
        "graph": problem.graph,
        "option_graphs": option_graphs,
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
            used.add(problem.key)
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
        "level": "",
    }


def build_worksheet(lesson_code: str, count: int, seed: int | None = None, level: str | None = None) -> dict:
    lesson = selectors.lessons().filter(code=lesson_code).first()
    if lesson is None or lesson_code not in available_lessons():
        raise UnknownLessonError(lesson_code)
    seed = new_seed() if seed is None else seed
    rng = random.Random(seed)  # noqa: S311 — بذرة قابلة للإعادة، لا استعمال أمني
    used: set[str] = set()
    questions = []
    for number in range(1, count + 1):
        try:
            problem = generate(lesson.code, rng, BlueprintItem.Kind.ESSAY, used, level)
        except LevelUnavailableError as error:
            raise UnknownLessonError(lesson_code) from error
        used.add(problem.key)
        slot = PartSlot("", lesson.code, lesson.title, BlueprintItem.Kind.ESSAY, 0)
        questions.append(
            {"number": number, "kind": slot.kind, "marks": 0, "parts": [render_part(problem, slot, rng)]}
        )
    return {
        "title": f"ورقة عمل: {lesson.title}" + (f" ({LEVEL_NAMES[level]})" if level else ""),
        "seed": seed,
        "total_marks": 0,
        "is_forecast": False,
        "level_marks": {},
        "questions": questions,
        "level": level or "",
    }
