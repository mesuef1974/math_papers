"""بنك الأسئلة التشخيصية: بنود موضوعية بمشتتات موسومة بنوع الخطأ، وبطاقة الخروج، واسترجاع متباعد متناوب.

منطق نقي بلا Django: يقرأ مولّدات `generators.REGISTRY` ولا يخترع مسائل. كل مشتتّ يحمل نوع الخطأ الذي ولّده
(`Problem.wrong_kinds` الموسوم داخل المولّد)، فاختيار الطالب لخيار خاطئ يكشف سوء فهمه بلا تصنيف آلي بعدي.
حتمي من (المقرر، الدرس، الصيغة، البذرة): البند نفسه يعود نفسه، وتتبدل الأعداد بتبدّل البذرة.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, replace

from .answer_positions import balanced_positions
from .generators import (
    ERROR_KINDS,
    REGISTRY,
    Generator,
    Problem,
    skill_example,
    variant_profile,
)

OPTION_COUNT = 4  # الصحيح وثلاثة مشتتات


class ItemBankError(LookupError):
    """لا بند يطابق الطلب."""


@dataclass(frozen=True)
class Option:
    text: str
    correct: bool
    kind: str | None  # مفتاح من ERROR_KINDS للمشتتّ، وNone للصحيح

    @property
    def misconception(self) -> str | None:
        return ERROR_KINDS[self.kind] if self.kind else None


@dataclass(frozen=True)
class Item:
    course: str
    lesson: str
    variant: str
    example: int | None  # مثال الكتاب الذي تقيس مهارته الصيغة
    level: str
    stem: str
    options: tuple[Option, ...]
    steps: tuple[str, ...]
    fingerprint: str
    graph: dict | None = None

    @property
    def answer_index(self) -> int:
        return next(i for i, option in enumerate(self.options) if option.correct)

    def diagnose(self, index: int) -> str | None:
        """سوء الفهم الذي يكشفه اختيار هذا الخيار، أو None إن كان صحيحًا."""
        return self.options[index].misconception


def usable(fn: Generator) -> bool:
    """صيغة تعطي بندًا موضوعيًا نصّي الخيارات (الرسوم الخيارية خارج هذه المرحلة)."""
    _, mcq_ok, _, _ = variant_profile(fn)
    return mcq_ok


def _rng(course: str, lesson: str, name: str, seed: int, index: int) -> random.Random:
    return random.Random(f"{course}|{lesson}|{name}|{seed}|{index}")  # noqa: S311 — بذور ثابتة لا أمنية


def build_item(
    problem: Problem, *, course: str, example: int | None, position: int, rng: random.Random
) -> Item:
    """يحوّل مسألة موسومة إلى بند، والصحيح في الموضع `position` والمشتتات مخلوطة في الباقي."""
    if problem.option_graphs or not problem.wrong:
        raise ItemBankError(f"{problem.lesson}/{problem.variant}: لا خيارات نصية")
    if len(problem.wrong_kinds) != len(problem.wrong):
        raise ItemBankError(f"{problem.lesson}/{problem.variant}: مشتتات بلا وسم")
    wrong = [Option(text, False, kind) for text, kind in zip(problem.wrong, problem.wrong_kinds, strict=True)]
    rng.shuffle(wrong)
    options = [*wrong]
    options.insert(position, Option(problem.answer, True, None))
    return Item(
        course=course,
        lesson=problem.lesson,
        variant=problem.variant,
        example=example,
        level=problem.level,
        stem=problem.stem,
        options=tuple(options),
        steps=problem.steps,
        fingerprint=problem.fingerprint,
        graph=problem.graph,
    )


def _generate(course: str, lesson: str, fn: Generator, seed: int, index: int) -> Problem:
    return replace(fn(_rng(course, lesson, fn.__name__, seed, index)), variant=fn.__name__)


def _items(course: str, picks: Sequence[tuple[str, Generator, int]], seed: int) -> list[Item]:
    """يبني بنودًا من (درس، صيغة، رقم) بمواضع صحيح متوازنة لا تتكدس على رمز واحد."""
    positions = balanced_positions(len(picks), OPTION_COUNT, random.Random(f"{course}|pos|{seed}"))  # noqa: S311
    items = []
    for (lesson, fn, index), position in zip(picks, positions, strict=True):
        problem = _generate(course, lesson, fn, seed, index)
        rng = _rng(course, lesson, fn.__name__, seed, index + 10_000)
        example = skill_example(course, lesson, fn.__name__)
        items.append(build_item(problem, course=course, example=example, position=position, rng=rng))
    return items


def _distinct(course: str, lesson: str, fn: Generator, seed: int, count: int) -> list[int]:
    """أرقام توليد تعطي مسائل مختلفة النص، حتى لا يتكرر البند في البنك."""
    seen: set[str] = set()
    indexes: list[int] = []
    for index in range(count * 8):
        problem = _generate(course, lesson, fn, seed, index)
        if problem.key not in seen:
            seen.add(problem.key)
            indexes.append(index)
        if len(indexes) == count:
            break
    return indexes


def bank(course: str, lesson: str, *, per_variant: int = 3, seed: int = 0) -> list[Item]:
    """بنك الدرس: لكل صيغة موضوعية `per_variant` بنودًا مختلفة، بمواضع إجابة متوازنة."""
    fns = [fn for fn in REGISTRY.get((course, lesson), []) if usable(fn)]
    if not fns:
        raise ItemBankError(f"لا صيغ موضوعية للدرس {lesson} في {course}")
    picks = [(lesson, fn, i) for fn in fns for i in _distinct(course, lesson, fn, seed, per_variant)]
    return _items(course, picks, seed)


def exit_ticket(course: str, lesson: str, example: int, *, seed: int = 0) -> Item:
    """بند بطاقة الخروج لمهارة مثال بعينه من الدرس (أول صيغة موضوعية تقيس ذلك المثال)."""
    for fn in REGISTRY.get((course, lesson), []):
        if usable(fn) and skill_example(course, lesson, fn.__name__) == example:
            return _items(course, [(lesson, fn, _distinct(course, lesson, fn, seed, 1)[0])], seed)[0]
    raise ItemBankError(f"لا صيغة موضوعية للمثال {example} في الدرس {lesson}")


def retrieval(course: str, earlier: Sequence[str], *, count: int = 3, seed: int = 0) -> list[Item]:
    """استرجاع متباعد متناوب من دروس سابقة: بند من كل درس بالتناوب، والدرس نفسه لا يتكرر متتاليًا ما أمكن.

    الدروس بترتيبها المعطى، وفي الدرس الواحد تدور الصيغ فلا تتكرر قبل أن تُستنفد.
    """
    pools = {lesson: [fn for fn in REGISTRY.get((course, lesson), []) if usable(fn)] for lesson in earlier}
    lessons = [lesson for lesson in earlier if pools[lesson]]
    if not lessons:
        raise ItemBankError("لا دروس سابقة بصيغ موضوعية")
    turn = dict.fromkeys(lessons, 0)
    picks: list[tuple[str, Generator, int]] = []
    while len(picks) < count:
        for lesson in lessons:
            if len(picks) == count:
                break
            pool = pools[lesson]
            fn = pool[turn[lesson] % len(pool)]
            round_ = turn[lesson] // len(pool) + 1
            picks.append((lesson, fn, _distinct(course, lesson, fn, seed, round_)[-1]))
            turn[lesson] += 1
    return _items(course, picks, seed)
