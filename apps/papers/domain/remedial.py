"""الورقة العلاجية: وصفة ورقة من أخطاء طالب واحد في بنود بنك الأسئلة. نقي بلا Django ولا قاعدة.

لكل مثال أخطأ فيه الطالب جزء واحد على الأقل من صيغ ذلك المثال نفسها في `generators.REGISTRY`، بأعداد تخالف البند الذي
أخطأ فيه (`item_bank.exit_ticket` بالدرس والمثال وبذرة البند). حتمي من (المقرر، الأخطاء، البذرة): البذرة نفسها تعيد
الوصفة نفسها، وبذرة أخرى تبدّل الأعداد. لا مسألة تُخترع هنا ولا نص من كتاب.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, replace

from .generators import MAX_ATTEMPTS, REGISTRY, Generator, Problem, skill_example
from .item_bank import ItemBankError, exit_ticket

MAX_PARTS = 6  # ورقة تُحل في جلسة علاج واحدة
Target = tuple[str, int]  # (رمز الدرس، رقم المثال)


@dataclass(frozen=True)
class StudentError:
    """خطأ طالب في بند: الدرس ومثاله ونوع الخطأ (مفتاح من ERROR_KINDS)، وبذرة البند الذي أخطأ فيه."""

    lesson: str
    example: int
    error_kind: str
    seed: int = 0


@dataclass(frozen=True)
class RemedialPart:
    """جزء علاجي: مسألة من صيغة تقيس المثال الذي أخطأ فيه الطالب."""

    lesson: str
    example: int
    misses: int  # عدد أخطاء الطالب في بنود هذا المثال
    error_kinds: tuple[str, ...]  # أنواع أخطائه فيه، مرتبة بلا تكرار (للمفتاح)
    problem: Problem

    @property
    def variant(self) -> str:
        return self.problem.variant

    @property
    def fingerprint(self) -> str:
        return self.problem.fingerprint


@dataclass(frozen=True)
class RemedialRecipe:
    course: str
    seed: int
    parts: tuple[RemedialPart, ...] = ()
    # أمثلة أخطأ فيها ولم يدخل لها جزء: تجاوزها الحد الأعلى، أو لا صيغة تعطيها مسألة جديدة
    left_out: tuple[Target, ...] = ()

    @property
    def empty(self) -> bool:
        return not self.parts


def _code_order(code: str) -> tuple[tuple[int, int | str], ...]:
    """ترتيب رموز الدروس عدديًا: «1.10» بعد «1.9»."""
    return tuple((0, int(piece)) if piece.isdigit() else (1, piece) for piece in code.split("."))


def _target_order(target: Target) -> tuple[tuple[tuple[int, int | str], ...], int]:
    return _code_order(target[0]), target[1]


def example_generators(course: str, lesson: str, example: int) -> list[Generator]:
    """صيغ الدرس التي تقيس مهارة المثال، بترتيب تسجيلها."""
    return [
        fn
        for fn in REGISTRY.get((course, lesson), [])
        if skill_example(course, lesson, fn.__name__) == example
    ]


def original_fingerprints(course: str, errors: Iterable[StudentError]) -> dict[Target, set[str]]:
    """بصمات البنود التي أخطأ فيها الطالب لكل مثال: الجزء العلاجي لا يكرر أيًّا منها."""
    found: dict[Target, set[str]] = {}
    for error in errors:
        prints = found.setdefault((error.lesson, error.example), set())
        try:
            prints.add(exit_ticket(course, error.lesson, error.example, seed=error.seed).fingerprint)
        except ItemBankError:
            continue  # بند لم يعد في البنك (حُذفت صيغته): لا أصل يُخالَف
    return found


def allocation(misses: Counter[Target], max_parts: int) -> dict[Target, int]:
    """عدد أجزاء كل مثال: جولات بترتيب الأكثر خطأً، جزء في الجولة، ولا مثال يزيد على عدد أخطائه.

    فالمثال الأكثر تكرارًا يُقدَّم حين يضيق الحد، وكل مثال ينال جزءًا قبل أن ينال غيره ثانيًا.
    """
    ranked = sorted(misses, key=lambda target: (-misses[target], _target_order(target)))
    counts: dict[Target, int] = {}
    left = max(max_parts, 0)
    round_ = 1
    while left and any(misses[target] >= round_ for target in ranked):
        for target in ranked:
            if left and misses[target] >= round_:
                counts[target] = round_
                left -= 1
        round_ += 1
    return counts


def _fresh_problem(
    course: str, target: Target, fns: list[Generator], position: int, seed: int, avoid: set[str]
) -> Problem | None:
    """مسألة للجزء `position` من المثال ببصمة ليست في `avoid`: تدور على صيغ المثال بدءًا من دور الجزء."""
    lesson, example = target
    for turn in range(len(fns)):
        fn = fns[(position + turn) % len(fns)]
        rng = random.Random(  # noqa: S311 — بذرة قابلة للإعادة، لا استعمال أمني
            f"{course}|{lesson}|{example}|{fn.__name__}|remedial|{seed}|{position}"
        )
        for _ in range(MAX_ATTEMPTS):
            problem = replace(fn(rng), variant=fn.__name__)
            if problem.fingerprint not in avoid:
                return problem
    return None


def remedial_recipe(
    course: str, errors: Iterable[StudentError], seed: int, *, max_parts: int = MAX_PARTS
) -> RemedialRecipe:
    """وصفة الورقة العلاجية لطالب من أخطائه. بلا أخطاء: وصفة فارغة.

    الأجزاء بترتيب الدرس فالمثال (ترتيب الإدخال لا يغيّرها)، وعددها لا يتجاوز `max_parts`.
    """
    errors = list(errors)
    misses = Counter((error.lesson, error.example) for error in errors)
    kinds: dict[Target, set[str]] = {}
    for error in errors:
        kinds.setdefault((error.lesson, error.example), set()).add(error.error_kind)
    originals = original_fingerprints(course, errors)
    counts = allocation(misses, max_parts)

    used: set[str] = set()
    parts: list[RemedialPart] = []
    left_out: list[Target] = []
    for target in sorted(misses, key=_target_order):
        fns = example_generators(course, *target)
        built = 0
        for position in range(counts.get(target, 0)):
            problem = _fresh_problem(course, target, fns, position, seed, originals[target] | used)
            if problem is None:
                break
            used.add(problem.fingerprint)
            built += 1
            parts.append(
                RemedialPart(
                    lesson=target[0],
                    example=target[1],
                    misses=misses[target],
                    error_kinds=tuple(sorted(kinds[target] - {""})),
                    problem=problem,
                )
            )
        if not built:
            left_out.append(target)
    return RemedialRecipe(course=course, seed=seed, parts=tuple(parts), left_out=tuple(left_out))
