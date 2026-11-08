"""تجميع الأوراق (قراءة فقط: البذرة نفسها تعطي الورقة نفسها دائمًا) وحفظ ترويسة الطباعة."""

from __future__ import annotations

import logging
import random
import secrets
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from apps.core.services import record_audit
from apps.curriculum import selectors
from apps.curriculum.models import BlueprintItem

from .domain.generators import (
    LEVEL_NAMES,
    LevelUnavailableError,
    Problem,
    available_lessons,
    generate,
    generator_version,
)
from .models import PrintProfile
from .selectors import PROFILE_FIELDS, print_profile

logger = logging.getLogger(__name__)

MAX_SEED = 2**31 - 1
PART_LABELS = "ABCDEFGH"
OPTION_LABELS = "أبجد"  # تطابق ترتيب عرض الخيارات في الواجهة


class UnknownBlueprintError(LookupError):
    pass


class UnknownLessonError(LookupError):
    pass


@dataclass(frozen=True)
class PartSlot:
    """خانة في الورقة: قيودها تُحفظ مع الجزء حتى يُستبدل أو يُعاد توليده بالقيود نفسها."""

    label: str
    lesson: str
    lesson_title: str
    kind: str
    marks: int
    level: str = ""  # فارغ = أي مستوى
    needs_graph: bool = False


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
        "variant": problem.variant,
        "fingerprint": problem.fingerprint,
        "slot": {"kind": slot.kind, "level": slot.level, "needs_graph": slot.needs_graph},
    }


def generate_for_slot(item: BlueprintItem, rng: random.Random, used: set[str]) -> Problem:
    """مسألة بمستوى الخانة ورسمها. خانة لا صيغة لها (عُدّلت من لوحة الإدارة) تُملأ بلا قيد بدل إسقاط الاختبار."""
    try:
        return generate(item.lesson.code, rng, item.kind, used, item.level or None, item.needs_graph)
    except LevelUnavailableError:
        logger.warning("خانة الجدول %s بلا صيغة مطابقة؛ تُملأ بلا قيد المستوى والرسم", item.pk)
        return generate(item.lesson.code, rng, item.kind, used)


def paper_meta(kind: str, **extra: object) -> dict:
    """حقول مشتركة تهم الحفظ وإعادة التوليد."""
    return {"kind": kind, "generator_version": generator_version(), **extra}


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
            slot = PartSlot(
                label,
                item.lesson.code,
                item.lesson.title,
                item.kind,
                item.marks,
                item.level or "",
                item.needs_graph,
            )
            problem = generate_for_slot(item, rng, used)
            used.add(problem.key)
            level_marks[problem.level] += item.marks
            parts.append(render_part(problem, slot, rng))
        questions.append(
            {"number": number, "kind": items[0].kind, "marks": sum(i.marks for i in items), "parts": parts}
        )
    return {
        **paper_meta("exam", blueprint=blueprint.slug, lesson_code=""),
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
        slot = PartSlot("", lesson.code, lesson.title, BlueprintItem.Kind.ESSAY, 0, level or "")
        questions.append(
            {"number": number, "kind": slot.kind, "marks": 0, "parts": [render_part(problem, slot, rng)]}
        )
    return {
        **paper_meta("worksheet", blueprint="", lesson_code=lesson.code),
        "title": f"ورقة عمل: {lesson.title}" + (f" ({LEVEL_NAMES[level]})" if level else ""),
        "seed": seed,
        "total_marks": 0,
        "is_forecast": False,
        "level_marks": {},
        "questions": questions,
        "level": level or "",
    }


@transaction.atomic
def save_print_profile(user: AbstractBaseUser, data: dict[str, Any]) -> dict[str, Any]:
    """يحفظ ترويسة المعلم (idempotent: الحفظ نفسه مرتين لا يغيّر شيئًا ولا يسجّل تدقيقًا ثانيًا)."""
    row, created = PrintProfile.objects.get_or_create(user=user)
    changed = [name for name in PROFILE_FIELDS if name in data and getattr(row, name) != data[name]]
    for name in changed:
        setattr(row, name, data[name])
    if changed or created:
        row.save()
        record_audit(
            action="print_profile.save", actor=user, target=user.get_username(), payload={"fields": changed}
        )
    return print_profile(user)
