"""باقة الحصة (المرحلة 1 من docs/lesson_package_plan.md): أوراق الحصة وفهرسها مشتقة من تحضيرها. نقي حتمي بلا قاعدة.

التحضير هو المصدر الوحيد: تمارين الكتاب بأرقامها وصفحاتها كما وزّعها، وبطاقتا الفحص والخروج بنداهما المعروضان
(`check_items.period_items`)، والمولَّد من صيغ مثال التمرين ببذرة من هوية الحصة. التمرين المحجوب ربطه (آلي لم يُعتمد)
لا يدخل ورقة طالب، ويحل المولَّد محله. التحضير (Word) والعرض خارج هذا الوصف: ملفاهما قائمان.
"""

from __future__ import annotations

import random
from collections.abc import Collection, Mapping
from dataclasses import dataclass, replace

from apps.papers.domain.book_source import book_ref
from apps.papers.domain.generators import REGISTRY, Problem, skill_example, variant_profile
from apps.papers.domain.item_bank import Item

from .check_items import PeriodItems, items_seed
from .prep import PeriodPrep, PrepExample

CLASSWORK, BASIC, ADVANCED, HOMEWORK = "classwork", "basic", "advanced", "homework"
FORMATIVE, EXIT, QUIZ = "formative", "exit", "quiz"
TITLES = {
    CLASSWORK: "ورقة التدريب الصفي",
    BASIC: "ورقة التمايز: أساسي",
    ADVANCED: "ورقة التمايز: متقدم",
    HOMEWORK: "ورقة الواجب",
    FORMATIVE: "بطاقة الفحص التكويني",
    EXIT: "بطاقة الخروج",
    QUIZ: "اختبار الدرس",
}
CARDS_PER_PAGE = {EXIT: 4}
LOW_LEVELS, HIGH_LEVELS = ("K", "A", "R"), ("R", "A", "K")
DEPTH_LEVELS = {1: LOW_LEVELS, 2: ("A", "K", "R")}  # وما فوق: HIGH_LEVELS
SEED_TRIES = 8


@dataclass(frozen=True)
class BookEntry:
    """تمرين من كتاب الطالب برقمه وصفحته وحدهما."""

    example: int
    dok: int
    number: int
    page: int | None


@dataclass(frozen=True)
class GeneratedEntry:
    example: int
    variant: str
    seed: str
    problem: Problem


@dataclass(frozen=True)
class ItemEntry:
    """بند موضوعي من التحضير نفسه (فحص أو خروج)."""

    item: Item

    @property
    def example(self) -> int | None:
        return self.item.example


Entry = BookEntry | GeneratedEntry | ItemEntry


@dataclass(frozen=True)
class Sheet:
    kind: str
    title: str
    entries: tuple[Entry, ...]
    objectives: tuple[tuple[int, str], ...]  # (المثال، نص هدفه) لأمثلة بنود الورقة
    per_page: int = 1
    example_pages: tuple[tuple[int, int], ...] = ()  # (المثال، صفحته) المعروفة


@dataclass(frozen=True)
class Note:
    """سطر في فهرس الباقة يشرح ما غاب أو استُبدل."""

    code: str  # empty | blocked | no_form | text_question
    message: str


@dataclass(frozen=True)
class LessonPackage:
    course: str
    lesson: str
    k: int
    sheets: tuple[Sheet, ...]
    notes: tuple[Note, ...]

    def sheet(self, kind: str) -> Sheet | None:
        return next((s for s in self.sheets if s.kind == kind), None)


class _Composer:
    def __init__(self, prep: PeriodPrep, items: PeriodItems, blocked: Collection[int]):
        self.prep, self.items, self.blocked = prep, items, frozenset(blocked)
        self.notes: list[Note] = []
        self.by_n = {e.n: e for e in prep.practice_examples}
        shown = [*items.formative.values(), *items.warmup, *([items.exit] if items.exit else [])]
        self.used = {item.fingerprint for item in shown}  # لا تكرر ورقةٌ بندًا معروضًا ولا مسألة ورقة أخرى
        self.seed = items_seed(prep)

    def note(self, code: str, message: str) -> None:
        note = Note(code, message)
        if note not in self.notes:
            self.notes.append(note)

    def book(self, kind: str, numbers: Collection[int]) -> list[BookEntry]:
        out = []
        for number in numbers:
            if number in self.blocked:
                self.note(
                    "blocked",
                    f"{TITLES[kind]}: {book_ref('التمرين', number, self.prep.exercise_pages.get(number))} ربطه لم يُعتمد",
                )
                continue
            for example in self.prep.practice_examples:
                dok = example.dok_of(number)
                if dok is not None:
                    out.append(BookEntry(example.n, dok, number, self.prep.exercise_pages.get(number)))
                    break
        return out

    def generated(self, kind: str, example: PrepExample, levels: tuple[str, ...]) -> GeneratedEntry | None:
        """مسألة من صيغ المثال بأقرب مستوى مطلوب لا تطابق ما سبقها؛ None إن لم تكن له صيغة أو نفدت."""
        pool = [
            fn
            for fn in REGISTRY.get((self.prep.course, self.prep.lesson), [])
            if skill_example(self.prep.course, self.prep.lesson, fn.__name__) == example.n
            and variant_profile(fn)[2]
        ]
        best: tuple[int, GeneratedEntry] | None = None
        for fn in pool:
            for attempt in range(SEED_TRIES):
                seed = f"{self.seed}|{kind}|{example.n}|{fn.__name__}|{attempt}"
                problem = replace(fn(random.Random(seed)), variant=fn.__name__)  # noqa: S311 — بذرة ثابتة
                if problem.fingerprint in self.used:
                    continue
                rank = levels.index(problem.level)
                if best is None or rank < best[0]:
                    best = rank, GeneratedEntry(example.n, fn.__name__, seed, problem)
        if best is None:
            if not example.conceptual:
                self.note(
                    "no_form",
                    f"{book_ref('المثال', example.n, example.page)}: لا صيغة تعطي مسألة لـ{TITLES[kind]}",
                )
            return None
        self.used.add(best[1].problem.fingerprint)
        return best[1]

    def classwork(self) -> list[Entry]:
        out: list[Entry] = []
        for c in self.prep.classwork:
            book = self.book(CLASSWORK, c.exercises)
            if book:
                out += book
            elif found := self.generated(CLASSWORK, self.by_n[c.example], LOW_LEVELS):
                out.append(found)
        return out

    def tier(self, kind: str, numbers: Collection[int], levels: tuple[str, ...]) -> list[Entry]:
        """مسار تمايز: تمارين الكتاب ومعها مسألة مولَّدة لكل مثال فيها."""
        if not numbers:
            return []
        book = self.book(kind, numbers)
        examples = sorted({e.example for e in book}) or [e.n for e in self.prep.practice_examples]
        extra = [self.generated(kind, self.by_n[n], levels) for n in examples]
        return [*book, *(e for e in extra if e)]

    def homework(self) -> list[Entry]:
        book = self.book(HOMEWORK, self.prep.homework)
        if book or not self.prep.homework:
            return list(book)
        found = [self.generated(HOMEWORK, e, LOW_LEVELS) for e in self.prep.practice_examples]
        return [e for e in found if e]

    def quiz(self) -> list[Entry]:
        measurable = [e for e in self.prep.practice_examples if e.has_generator and not e.conceptual]
        out: list[Entry] = []
        for i, depth in enumerate(self.prep.quiz):
            if not measurable:
                break
            example = measurable[i % len(measurable)]
            if found := self.generated(QUIZ, example, DEPTH_LEVELS.get(depth, HIGH_LEVELS)):
                out.append(found)
        return out

    def cards(self) -> tuple[list[Entry], list[Entry]]:
        for n in self.prep.formative:
            if n not in self.items.formative:
                self.note(
                    "text_question",
                    f"{book_ref('المثال', n, self.prep.pages.get(n))}: فحصه سؤال نصّي في التحضير بلا بطاقة",
                )
        if self.prep.exit_ticket and not self.items.exit:
            n = self.prep.exit_ticket.example
            self.note(
                "text_question",
                f"{book_ref('المثال', n, self.prep.pages.get(n))}: سؤال خروجه نصّي في التحضير بلا بطاقة",
            )
        formative: list[Entry] = [ItemEntry(self.items.formative[n]) for n in sorted(self.items.formative)]
        return formative, [ItemEntry(self.items.exit)] if self.items.exit else []


def compose_package(
    prep: PeriodPrep,
    items: PeriodItems,
    *,
    objectives: Mapping[int, str],
    blocked: Collection[int] = (),
) -> LessonPackage:
    """`objectives` نصوص أهداف أمثلة الدرس كلها (الحصة الأخيرة تراجعها)، و`blocked` أرقام تمارين لم يُعتمد ربطها."""
    composer = _Composer(prep, items, blocked)
    formative, ticket = composer.cards()
    parts: dict[str, list[Entry]] = {
        CLASSWORK: composer.classwork(),
        BASIC: composer.tier(BASIC, prep.basic, LOW_LEVELS),
        ADVANCED: composer.tier(ADVANCED, prep.advanced, HIGH_LEVELS),
        HOMEWORK: composer.homework(),
        FORMATIVE: formative,
        EXIT: ticket,
        QUIZ: composer.quiz(),
    }
    sheets = []
    for kind, entries in parts.items():
        if not entries:
            composer.note("empty", f"{TITLES[kind]}: لا بنود لها في تحضير هذه الحصة")
            continue
        numbers = sorted({e.example for e in entries if e.example is not None})
        sheets.append(
            Sheet(
                kind,
                TITLES[kind],
                tuple(entries),
                tuple((n, objectives[n]) for n in numbers if n in objectives),
                CARDS_PER_PAGE.get(kind, 1),
                tuple((n, page) for n in numbers if (page := prep.pages.get(n))),
            )
        )
    return LessonPackage(prep.course, prep.lesson, prep.k, tuple(sheets), tuple(composer.notes))


def package_problems(
    prep: PeriodPrep, items: PeriodItems, package: LessonPackage, blocked: Collection[int] = ()
) -> dict[str, list[str]]:
    """معايير الباقة الحاجبة B1 إلى B5: رمز المعيار → مخالفاته (الفارغ ناجح)."""
    found: dict[str, list[str]] = {code: [] for code in ("B1", "B2", "B3", "B4", "B5")}
    expected = {
        CLASSWORK: prep.classwork,
        BASIC: prep.basic,
        ADVANCED: prep.advanced,
        HOMEWORK: prep.homework,
        FORMATIVE: items.formative,
        EXIT: items.exit,
        QUIZ: prep.quiz,
    }
    found["B1"] = [TITLES[kind] for kind, source in expected.items() if source and not package.sheet(kind)]
    shown = {
        FORMATIVE: {item.fingerprint for item in items.formative.values()},
        EXIT: {items.exit.fingerprint} if items.exit else set(),
    }
    for kind, wanted in shown.items():
        sheet = package.sheet(kind)
        printed = {e.item.fingerprint for e in sheet.entries if isinstance(e, ItemEntry)} if sheet else set()
        if printed != wanted:
            found["B3"].append(f"{TITLES[kind]}: بنودها غير بنود التحضير")
    for sheet in package.sheets:
        described = {n for n, text in sheet.objectives if text}
        for entry in sheet.entries:
            if isinstance(entry, GeneratedEntry) and not entry.problem.answer:
                found["B2"].append(f"{sheet.title}: {entry.variant} بلا إجابة")
            if isinstance(entry, BookEntry) and entry.number in blocked:
                found["B4"].append(f"{sheet.title}: التمرين {entry.number}")
            if entry.example not in described:
                found["B5"].append(f"{sheet.title}: بند المثال {entry.example} بلا هدف")
    return found
