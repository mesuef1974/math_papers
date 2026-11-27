"""بنود الفحص التكويني وبطاقة الخروج من بنك الأسئلة (`apps/papers/domain/item_bank.py`): نقي حتمي بلا قراءة قاعدة.

لكل مثال في `prep.formative` بند، ولبطاقة الخروج بند لمثالها، ببذرة مشتقة من هوية الحصة فيبقى التحضير والعرض حتميين.
مثال بلا بند موضوعي نصّي (لا صيغة موضوعية أو رسم خياري أو نص أطول من سطرين) يبقى «سؤالًا من مهارة المثال» كما كان.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from apps.papers.domain.bidi import isolate_number_ranges, strip_isolation
from apps.papers.domain.generators import ERROR_KINDS
from apps.papers.domain.item_bank import Item, ItemBankError, exit_ticket, retrieval

from .plain_math import convertible, plain_math
from .prep import PeriodPrep

OPTION_LETTERS = ("أ", "ب", "ج", "د")
MAX_ITEM_LINES = 2
SEED_TRIES = 8
ITEM_LINE_CHARS = 60  # كـ `deck.LINE_CHARS`: حروف السطر بخط 24pt


@dataclass(frozen=True)
class PeriodItems:
    formative: dict[int, Item]  # مثال -> بنده، والغائب يبقى سؤالًا نصيًّا
    exit: Item | None
    retrieval: Item | None = None  # استرجاع متباعد في شريحة التذكّر للحصة الأولى من الدرس
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
    texts = (item.stem, *(o.text for o in item.options))
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


def _retrieval_item(prep: PeriodPrep, seed: int) -> Item | None:
    """بند من درس سابق متباعد: يُدار ترتيب الدروس ببذرة الحصة فلا يقع الاستدعاء على أول درس دائمًا، ويُستبعد الدرس
    السابق مباشرة ما دام غيره موجودًا (استدعاؤه في ربط الحصة نفسه)."""
    earlier = prep.earlier_lessons[:-1] or prep.earlier_lessons
    if prep.k != 1 or not earlier:
        return None
    turn = seed % len(earlier)
    ordered = [*earlier[turn:], *earlier[:turn]]
    for attempt in range(SEED_TRIES):
        try:
            item = retrieval(prep.course, ordered, count=1, seed=seed + attempt * 2)[0]
        except ItemBankError:
            return None
        if fits_slide(item):
            return item
    return None


def period_items(prep: PeriodPrep) -> PeriodItems:
    seed = items_seed(prep)
    formative = {}
    for n in prep.formative:
        item = _item(prep, n, seed)
        if item is not None:
            formative[n] = item
    found = _seeded_item(prep, prep.exit_ticket.example, seed + 1) if prep.exit_ticket else None
    ticket, ticket_seed = found or (None, None)
    return PeriodItems(
        formative=formative, exit=ticket, retrieval=_retrieval_item(prep, seed + 2), exit_seed=ticket_seed
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
