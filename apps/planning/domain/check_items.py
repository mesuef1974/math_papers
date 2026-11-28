"""بنود التقييم البنائي وبطاقة الخروج من بنك الأسئلة (`apps/papers/domain/item_bank.py`): نقي حتمي بلا قراءة قاعدة.

لكل مثال في `prep.formative` بند، ولبطاقة الخروج بند لمثالها، ببذرة مشتقة من هوية الحصة فيبقى التحضير والعرض حتميين.
مثال بلا بند موضوعي نصّي (لا صيغة موضوعية أو رسم خياري أو نص أطول من سطرين) يبقى «سؤالًا من مهارة المثال» كما كان.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass, field

from apps.papers.domain.bidi import isolate_number_ranges, strip_isolation
from apps.papers.domain.generators import ERROR_KINDS, Problem
from apps.papers.domain.item_bank import (
    Item,
    ItemBankError,
    exit_ticket,
    open_problems,
    prerequisite,
    retrieval,
    skill_examples,
)

from .plain_math import convertible, plain_math
from .prep import PeriodPrep

OPTION_LETTERS = ("أ", "ب", "ج", "د")
MAX_ITEM_LINES = 2
WARMUP_QUESTIONS = 2
SEED_TRIES = 8
ITEM_LINE_CHARS = 60  # كـ `deck.LINE_CHARS`: حروف السطر بخط 24pt


@dataclass(frozen=True)
class OpenQuestion:
    """سؤال محدد بإجابته بلا خيارات: لما لا بند موضوعي له أو لا تتسع دقائق الغلق لشريحة بنده (قرار المالك 2026-11-28)."""

    example: int
    seed: str
    problem: Problem


@dataclass(frozen=True)
class PeriodItems:
    formative: dict[int, Item]  # مثال -> بنده، والغائب يبقى سؤالًا نصيًّا
    exit: Item | None
    warmup: tuple[Item, ...] = ()  # سؤالا التهيئة: من الحصة أو الدرس السابق، ثم استرجاع من أقدم
    open: dict[int, OpenQuestion] = field(default_factory=dict)  # مثال التقييم البنائي -> سؤاله المقالي
    exit_open: OpenQuestion | None = None  # سؤال الخروج حين لا بند موضوعي له
    exit_seed: int | None = (
        None  # البذرة التي ولّدت `exit` فعلًا: بها يُعاد البند نفسه عند إدخال النتائج وتصحيحها
    )


def items_seed(prep: PeriodPrep) -> int:
    """بذرة الحصة: من مقررها ودرسها ورقمها، لا من الوقت ولا من ترتيب الاستدعاء."""
    digest = hashlib.sha256(f"items|{prep.course}|{prep.lesson}|{prep.k}|{prep.n}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % 1_000_000


def fits_slide(item: Item) -> bool:
    """بند يصلح للشريحة: بلا رسم، وسؤاله وكل خيار منه في سطرين على الأكثر (S6)."""
    if item.graph is not None:
        return False
    return _fits((item.stem, *(o.text for o in item.options)))


def _fits(texts: tuple[str, ...]) -> bool:
    if not all(convertible(t) for t in texts):  # مصفوفة أو أمر بلا تحويل مقروء: يبقى سؤالًا نصيًّا
        return False
    return all(
        math.ceil(len(strip_isolation(plain_math(t))) / ITEM_LINE_CHARS) <= MAX_ITEM_LINES for t in texts
    )


def _seeded_item(prep: PeriodPrep, example: int, seed: int, variant: int = 0) -> tuple[Item, int] | None:
    """أول بند يصلح للشريحة من بذور متتالية (السؤال الطويل يقصر ببذرة أخرى) مع بذرته الفعلية؛ None إن لم يصلح أيّ منها."""
    for attempt in range(SEED_TRIES):
        used = seed + attempt * 2
        try:
            item = exit_ticket(prep.course, prep.lesson, example, seed=used, variant=variant)
        except ItemBankError:
            return None
        if fits_slide(item):
            return item, used
    return None


def _item(prep: PeriodPrep, example: int, seed: int) -> Item | None:
    """بند التحقق من صيغة المثال الثانية (غير صيغة بطاقة الخروج) إن وُجدت وصلحت، وإلا من الأولى."""
    found = _seeded_item(prep, example, seed, variant=1) or _seeded_item(prep, example, seed)
    return None if found is None else found[0]


def _fitting(seed: int, build: Callable[[int], Item]) -> Item | None:
    for attempt in range(SEED_TRIES):
        try:
            item = build(seed + attempt * 2)
        except ItemBankError:
            return None
        if fits_slide(item):
            return item
    return None


def _previous_item(prep: PeriodPrep, seed: int) -> Item | None:
    """مهارة من الحصة السابقة (آخر أمثلتها أولًا: مهارة بطاقة خروجها)، وإلا من أقرب درس سابق."""
    for n in reversed(prep.previous_examples):
        found = _seeded_item(prep, n, seed)
        if found is not None:
            return found[0]
    for lesson in reversed(prep.earlier_lessons):
        for n in skill_examples(prep.course, lesson):
            item = _fitting(seed, lambda s, at=lesson, n=n: exit_ticket(prep.course, at, n, seed=s))
            if item is not None:
                return item
    return None


def _older_item(prep: PeriodPrep, seed: int, previous: Item | None) -> Item | None:
    """استرجاع من درس أقدم من درس السؤال الأول، بترتيب يُدار ببذرة الحصة فلا يقع دائمًا على أول درس."""
    if previous is None:
        return None
    earlier = prep.earlier_lessons
    older = earlier[: earlier.index(previous.lesson)] if previous.lesson in earlier else earlier
    turn = seed % len(older) if older else 0
    for lesson in (*older[turn:], *older[:turn]):
        item = _fitting(seed, lambda s, at=lesson: retrieval(prep.course, [at], count=1, seed=s)[0])
        if item is not None:
            return item
    return None


def _warmup_items(prep: PeriodPrep, seed: int) -> tuple[Item, ...]:
    """سؤالا التهيئة؛ ما لا مصدر سابقًا له يكمله مولّد المتطلب السابق للمقرر (مقرر بلا مولّد يبقى بما وُجد)."""
    previous = _previous_item(prep, seed)
    found = [item for item in (previous, _older_item(prep, seed + 1, previous)) if item is not None]
    for index in range(WARMUP_QUESTIONS - len(found)):
        item = _fitting(seed + 3, lambda s, i=index: prerequisite(prep.course, i, seed=s))
        if item is not None:
            found.append(item)
    return tuple(found)


def split_stem(stem: str) -> tuple[str, ...]:
    """نص السؤال في بند واحد، أو بندين كلٌّ منهما سطران (S6) يُقطع عند فراغ خارج الصيغة، والأولى بعد نقطة أو فاصلة؛
    الفارغ لما لا يتسع."""
    if _fits((stem,)):
        return (stem,)
    cuts = [i for i, c in enumerate(stem) if c == " " and stem[:i].count("$") % 2 == 0]
    cuts.sort(key=lambda i: (stem[i - 1] not in ".،؛؟:", abs(len(stem) - 2 * i)))
    for i in cuts:
        parts = (stem[:i], stem[i + 1 :])
        if all(_fits((part,)) for part in parts):
            return parts
    return ()


def book_exercise(prep: PeriodPrep, example: int) -> int | None:
    """تمرين الكتاب لمثال لا صيغة تعطي له سؤالًا يُعرض (جدول أو دالة متعددة التعريف أو رسم): أول تمرين من صفوفه لم تأخذه
    تدريبات الحصة ولا الواجب، وإلا أول تمارينه."""
    found = next((e for e in prep.practice_examples if e.n == example), None)
    if found is None:
        return None
    own = [x for _, exercises in found.all_rows for x in exercises]
    taken = {x for c in prep.classwork for x in c.exercises} | {*prep.basic, *prep.advanced, *prep.homework}
    return next((x for x in own if x not in taken), own[0] if own else None)


def _open_question(prep: PeriodPrep, example: int, kind: str, taken: set[str]) -> OpenQuestion | None:
    seed = f"{items_seed(prep)}|{kind}|{example}"
    found = [
        (problem, used)
        for problem, used in open_problems(prep.course, prep.lesson, example, seed=seed)
        if problem.fingerprint not in taken and split_stem(problem.stem)
    ]
    if not found:
        return None
    problem, used = min(
        found, key=lambda pair: len(split_stem(pair[0].stem))
    )  # الأقصر أولًا، ثم ترتيب التوليد
    taken.add(problem.fingerprint)
    return OpenQuestion(example, used, problem)


def split_check_questions(prep: PeriodPrep, items: PeriodItems) -> tuple[list[int], tuple[int, ...]]:
    """أمثلة التقييم البنائي بشريحة بند لكل منها، والباقي (بلا بند أو فوق ما تتسع له دقائق الغلق، شريحة بدقيقة على الأقل)
    أسئلة مقالية في شريحة واحدة."""
    closing = next((st.minutes for st in prep.stages if st.name == "closing"), 0)
    others = bool(prep.exit_ticket) + bool(prep.quiz) + bool(prep.homework)
    budget = max(closing - others, 0)
    with_item = [n for n in prep.formative if n in items.formative]
    as_open = [n for n in prep.formative if n not in items.formative]
    if len(with_item) + bool(as_open) > budget:
        keep = max(budget - 1, 0)
        as_open = [n for n in prep.formative if n not in with_item[:keep]]
        with_item = with_item[:keep]
    return with_item, tuple(as_open)


def period_items(prep: PeriodPrep) -> PeriodItems:
    seed = items_seed(prep)
    formative = {}
    for n in prep.formative:
        item = _item(prep, n, seed)
        if item is not None:
            formative[n] = item
    found = _seeded_item(prep, prep.exit_ticket.example, seed + 1) if prep.exit_ticket else None
    ticket, ticket_seed = found or (None, None)
    warmup = _warmup_items(prep, seed + 2)
    shown = [*formative.values(), *warmup, *([ticket] if ticket else [])]
    taken = {item.fingerprint for item in shown}
    opened = {n: q for n in prep.formative if (q := _open_question(prep, n, "formative", taken))}
    exit_open = None
    if prep.exit_ticket and ticket is None:
        exit_open = _open_question(prep, prep.exit_ticket.example, "exit", taken)
    return PeriodItems(
        formative=formative,
        exit=ticket,
        warmup=warmup,
        exit_seed=ticket_seed,
        open=opened,
        exit_open=exit_open,
    )


def item_stem(item: Item) -> str:
    """نص السؤال كما يُعرض على الطلاب: في شريحة البند وفي جدول إدخال النتائج."""
    return isolate_number_ranges(plain_math(item.stem))


def option_text(text: str) -> str:
    """نص الخيار كما يُعرض على الطلاب، بلا حرفه."""
    return isolate_number_ranges(plain_math(text))


def option_label(index: int, text: str) -> str:
    return isolate_number_ranges(f"{OPTION_LETTERS[index]}) {plain_math(text)}")


def item_words_source(item: Item) -> list[str]:
    """نصوص البند التي تدخل العرض: السؤال والخيارات وأوصاف أخطاء مشتتاتها."""
    return [
        plain_math(item.stem),
        *(plain_math(o.text) for o in item.options),
        *(o.misconception or "" for o in item.options),
    ]


def all_misconceptions() -> list[str]:
    return list(ERROR_KINDS.values())
