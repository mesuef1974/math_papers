"""عرض الحصة من تحضيرها (المرحلة 4 من `docs/lesson_prep_plan.md`): نموذج شرائح حتمي بلا Django ولا نص دليل.

المدخل الوحيد تحضير حصة ومقاطع أمثلتها: لكل شريحة مرحلتها من مراحل التحضير ودقائقها وملاحظات المتحدث، وكل نص فيها من
قوالب `PERIOD_TEXT` أو من سلوك هدف مؤلَّف معتمد. صور الأمثلة المقصوصة من كتاب الطالب تأتي من طبقة الأصول الخاصة ولا تدخل
المستودع. الناقص لا يُخمَّن: مثال بلا مقطع أو مقطع خارج الحصة خطأ لا تجاهل. معايير النموذج في `deck_checks.py`، والتصدير
ومعايير الملف (S7 وS8 وS12) في `pptx_export.py` و`pptx_checks.py`.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

from apps.papers.domain.bidi import isolate_number_ranges
from apps.papers.domain.book_source import book_ref, number_list, numbers_with_pages

from .calendar_engine import PlanningError
from .check_items import (
    OPTION_LETTERS,
    OpenQuestion,
    PeriodItems,
    book_exercise,
    period_items,
    split_check_questions,
    split_stem,
)
from .plain_math import plain_math
from .prep import PeriodPrep, PrepExample, prep_digest
from .prep_sheet import STAGE_LABELS, recall_label, split_minutes
from .slide_math import display, isolate_outside_math

REPRESENTATION_LABELS = {
    "بياني": "بياني",
    "جبري": "جبري",
    "سياق": "سياق حياتي",
    "جدولي": "جدولي",
    "لفظي": "لفظي",
}


class DeckError(PlanningError):
    """مدخل لا يصلح لبناء عرض."""


@dataclass(frozen=True)
class ExampleClip:
    """مثال مقصوص من صفحة الكتاب: صورة PNG بأبعادها ورقم المثال في الدرس. `part` 1 للمثال و2 فما فوق لتتمته («تابع المثال»)."""

    n: int
    png: bytes
    width_px: int
    height_px: int
    part: int = 1
    kind: str = "example"  # example | practice («حاول أن تحل» لمثال: مقطع التدريب من كتاب الطالب)
    cuts: tuple[int, ...] = ()  # صفوف قص المقطع الطويل (`example_clips.find_cuts`)؛ فارغ: يُعرض كما هو

    def __post_init__(self) -> None:
        if self.kind not in ("example", "practice"):
            raise DeckError(f"نوع مقطع غير معروف: {self.kind}")
        if self.part < 1:
            raise DeckError(f"جزء المثال {self.n} غير صالح")
        if self.width_px <= 0 or self.height_px <= 0:
            raise DeckError(f"أبعاد صورة المثال {self.n} غير صالحة")
        if not self.png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise DeckError(f"صورة المثال {self.n} ليست PNG")


# ---- عرض الحصة من تحضيرها ----

# الإعداد: أرقام التصميم في مكان واحد (افتراضات تُراجع بعد أول تجربة في الصف)
PERIOD_DECK_FORMAT = 15  # 15: شريحة المصطلحات؛ 14: سؤال محدد في التقييم البنائي والخروج؛ 13: سؤالا تهيئة بشريحتين؛ 12: المقطع الطويل يُقص عند فراغ أبيض؛ 11: سؤال التحقق من صيغة غير صيغة بطاقة الخروج؛ 10: اسم الدرس على الغلاف وبلا شريحة «حل المثال»؛ 9: صيغ الشرائح معادلات PowerPoint أصلية؛ 8: لا يُعزل المدى داخل تعبير رياضي؛ 7:صيغ LaTeX رموزًا مقروءة في البنود (6: شريط المراحل ودقائق المرحلة على الشريحة (5: بند الاسترجاع المتباعد في شريحة التذكّر؛ 4: بنود البنك في التحقق والخروج؛ 3: تخطيطات الماستر ورقم الشريحة)
MINUTES_PER_SLIDE = 2
TITLE_PT, BODY_PT = 36, 28
MIN_TITLE_PT, MIN_BODY_PT = 32, 24
MAX_BULLETS = 6
MAX_LINES = 2
LINE_CHARS = 60  # حروف السطر بخط 24pt في منطقة محتوى 16:9 (تقدير محافظ)

# لكل نوع شريحة مرحلته من مراحل التحضير
SLIDE_PHASE = {
    "title": "warmup",
    "recall": "warmup",
    "objectives": "objectives",
    "terms": "objectives",
    "example": "direct",
    "try": "guided",
    "classwork": "guided",
    "differentiation": "independent",
    "check": "closing",
    "exit": "closing",
    "quiz": "closing",
    "homework": "closing",
}
# شريط المراحل على كل شريحة بعد العنوان: اسم قصير لكل مرحلة، وشارة دقائق المرحلة الحالية (قرار المالك 2026-11-24: شارة ثابتة بلا
# برمجة؛ جانب الوقت في الملاحظات يبقى كما هو)
STAGE_SHORT = {
    "warmup": "التهيئة",
    "objectives": "الأهداف",
    "direct": "التعليم",
    "guided": "الموجَّهة",
    "independent": "المستقلة",
    "closing": "الغلق",
}
MINUTES_BADGE = "{minutes} د"
CLIP_KINDS = frozenset({"example", "try"})

# قوالب كل نص في العرض (الشريحة والنص البديل والملاحظات)؛ S13 يقيس كلمات العرض بكلماتها
PERIOD_TEXT = {
    "title": "الدرس {lesson}",
    "period": "الحصة {k} من {n}",
    "standards": "المعايير: {codes}",
    "book_pages": "كتاب الطالب: ص {pages}",
    "recall_title": "تذكّر",
    "objectives_title": "أهداف الحصة",
    "terms_title": "المصطلحات",
    "term": "{ar} ({en})",
    "objective_pending": "{ref}: نص الهدف معلَّق",
    "objective_note": "{ref}: الشرط: {condition} · المعيار: {criterion}",
    "example_title": "{ref}",
    "continued_title": "تابع {ref}",
    "try_title": "حاول أن تحل: {ref}",
    "alt": "{ref} من كتاب الطالب",
    "try_continued_title": "تابع حاول أن تحل: {ref}",
    "try_alt": "حاول أن تحل: {ref} من كتاب الطالب",
    "classwork_title": "تدريب صفي: {ref}",
    "exercises": "حلّ تمارين الكتاب: {numbers}",
    "independent_title": "الممارسة المستقلة",
    "basic": "المسار الأساسي: تمارين الكتاب {numbers}",
    "advanced": "المسار المتقدم: تمارين الكتاب {numbers}",
    "check_title": "تحقّق من فهمك",
    "skill_question": "سؤال من مهارة {ref}",
    "open_note": "{ref}: الإجابة: {answer}",
    "book_question": "حلّ {exercise} من كتاب الطالب (مهارة {ref})",
    "book_note": "{exercise}: راجع إجابته في دليل المعلم",
    "exit_title": "بطاقة الخروج",
    "option_letters": "أ ب ج د",
    "answer_note": "الإجابة الصحيحة: {letter}",
    "distractor_note": "الخيار {letter}: {misconception}",
    "choose_justify_note": "اختر ثم برّر: يختار الطالب وحده قبل التفاعل ثم يكتب مبرره فرديًا بعده",
    "quiz_title": "اختبار الدرس",
    "quiz_count": "عدد الأسئلة {count}",
    "homework_title": "الواجب",
    "phase_note": "الطور: {phase}",
    "minutes_note": "الدقائق: {minutes}",
    "representations_note": "التمثيلات: {labels}",
    "depth_note": "عمق التمارين: {depths}",
    "exercise_depth_note": "{ref}: DOK {dok}",
    "differentiation_note": "الدعم بالمسار الأساسي لمن يحتاجه، والإثراء بالمسار المتقدم",
    "conceptual_note": "مثال مفاهيمي: أسئلة شفهية عن الاشتقاق بلا تدريب",
    "quiz_note": "أعماق الاختبار: {depths}",
}


@dataclass(frozen=True)
class PeriodSlide:
    """شريحة في عرض الحصة: نوعها ومرحلتها ودقائقها، و`refs` أرقام الأمثلة التي تخصها، والملاحظات للمعلم وحده."""

    kind: str
    phase: str
    title: str
    bullets: tuple[str, ...] = ()
    refs: tuple[int, ...] = ()
    clip: ExampleClip | None = None
    alt: str = ""
    minutes: int = 0
    notes: tuple[str, ...] = ()
    title_pt: int = TITLE_PT
    body_pt: int = BODY_PT
    rtl: bool = True

    @property
    def texts(self) -> tuple[str, ...]:
        """نصوص الشريحة كما تُقرأ (النقاط تحمل `$...$` ليكتبها التصدير معادلات)."""
        raw = (self.title, *self.bullets, *((self.alt,) if self.alt else ()), *self.notes)
        return tuple(display(t) for t in raw)


@dataclass(frozen=True)
class PeriodDeck:
    key: str
    course: str
    lesson: str
    k: int
    n: int
    minutes: int
    slides: tuple[PeriodSlide, ...]


def _t(name: str, **values: object) -> str:
    return isolate_number_ranges(PERIOD_TEXT[name].format(**values))


def deck_key_of(
    prep: PeriodPrep,
    clip_digests: Iterable[tuple[int, int, str]],
    practice_digests: Iterable[tuple[int, int, str]] = (),
) -> str:
    """مفتاح ملف العرض من تجزئة التحضير وتجزئة SHA-256 لكل مقطع (المثال، الجزء، التجزئة): يكفي فهرس الأصول لحسابه
    دون قراءة الصور، وتغيّر التحضير أو مقطع أو صيغة الملف يعطي مفتاحًا جديدًا."""
    digest = hashlib.sha256(f"{PERIOD_DECK_FORMAT}|{prep_digest(prep)}".encode())
    for n, part, sha in sorted(clip_digests):
        digest.update(f"|{n}.{part}:{sha}".encode())
    for n, part, sha in sorted(practice_digests):  # لاحقة لا تمسّ مفتاح عرض بلا مقاطع تدريب
        digest.update(f"|t{n}.{part}:{sha}".encode())
    return f"decks/{prep.course}/{prep.lesson}-k{prep.k}of{prep.n}-p{prep.minutes}-{digest.hexdigest()[:16]}.pptx"


def content_digest(sha256: str, cuts: Sequence[int] | None) -> str:
    """تجزئة المقطع كما يُعرض: قصّه يغيّر الشرائح والملف نفسه لم يتغير، فيدخل مفتاح العرض."""
    return f"{sha256}~{','.join(map(str, cuts))}" if cuts else sha256


def _clip_digest(clip: ExampleClip) -> tuple[int, int, str]:
    return clip.n, clip.part, content_digest(hashlib.sha256(clip.png).hexdigest(), clip.cuts)


def period_deck_key(prep: PeriodPrep, clips: Sequence[ExampleClip]) -> str:
    """`clips` مقاطع الأمثلة ومقاطع التدريب معًا؛ يفرزها النوع."""
    return deck_key_of(
        prep,
        (_clip_digest(c) for c in clips if c.kind == "example"),
        (_clip_digest(c) for c in clips if c.kind == "practice"),
    )


def objective_bullet(prep: PeriodPrep, index: int) -> str:
    """الهدف على الشريحة: سلوكه المعتمد بفعله (الشرط والمعيار في الملاحظات)، و«معلَّق» قبل اعتماد وحدته."""
    objective = prep.objectives[index]
    if prep.unit_status == "approved" and objective.behavior:
        return isolate_number_ranges(objective.behavior)
    n = objective.example
    return _t("objective_pending", ref=book_ref("مثال", n, prep.pages.get(n)))


def example_title(kind: str, example: PrepExample) -> str:
    """عنوان شريحة المثال برقم صفحته في كتاب الطالب حين تُعرف (قرار المالك 2026-11-20)؛ صفحة التتمة صفحة بدء المثال."""
    word = "المثال" if kind == "continued" else "مثال"
    return _t(f"{kind}_title", ref=book_ref(word, example.n, example.page))


def example_alt(example: PrepExample) -> str:
    return _t("alt", ref=book_ref("مثال", example.n, example.page))


def _clip_groups(prep: PeriodPrep, clips: Sequence[ExampleClip]) -> dict[int, tuple[ExampleClip, ...]]:
    seen = [(c.n, c.part) for c in clips]
    if len(set(seen)) != len(seen):
        raise DeckError("مقطع مكرر")
    outside = sorted({c.n for c in clips} - {e.n for e in prep.examples})
    if outside:
        raise DeckError(f"مقاطع لأمثلة خارج الحصة: {outside}")
    groups: dict[int, tuple[ExampleClip, ...]] = {}
    for e in prep.examples:
        mine = tuple(sorted((c for c in clips if c.n == e.n), key=lambda c: c.part))
        if not mine:
            raise DeckError(f"لا مقطع للمثال {e.n}")
        if [c.part for c in mine] != list(range(1, len(mine) + 1)):
            raise DeckError(f"أجزاء المثال {e.n} غير متصلة")
        groups[e.n] = mine
    return groups


def _practice_groups(prep: PeriodPrep, clips: Sequence[ExampleClip]) -> dict[int, tuple[ExampleClip, ...]]:
    """مقاطع «حاول أن تحل» لكل مثال: اختيارية (لا مقطع لمثال يبقى تدريبه نصًّا)، لكن مقطعًا لمثال خارج الحصة أو مكررًا أو
    بأجزاء غير متصلة خطأ لا تخمين."""
    seen = [(c.n, c.part) for c in clips]
    if len(set(seen)) != len(seen):
        raise DeckError("مقطع تدريب مكرر")
    outside = sorted({c.n for c in clips} - {e.n for e in prep.examples})
    if outside:
        raise DeckError(f"مقاطع تدريب لأمثلة خارج الحصة: {outside}")
    groups: dict[int, tuple[ExampleClip, ...]] = {}
    for e in prep.examples:
        mine = tuple(sorted((c for c in clips if c.n == e.n), key=lambda c: c.part))
        if not mine:
            continue
        if [c.part for c in mine] != list(range(1, len(mine) + 1)):
            raise DeckError(f"أجزاء تدريب المثال {e.n} غير متصلة")
        groups[e.n] = mine
    return groups


def try_alt(example: PrepExample) -> str:
    return _t("try_alt", ref=book_ref("مثال", example.n, example.page))


def _period_example_notes(example: PrepExample) -> tuple[str, ...]:
    notes = []
    if example.representations:
        labels = "، ".join(REPRESENTATION_LABELS.get(r, r) for r in example.representations)
        notes.append(_t("representations_note", labels=labels))
    if example.max_dok:  # عمق المثال من مصدر التحضير نفسه (هدفه وT2)، فلا يختلفان
        notes.append(_t("depth_note", depths=f"DOK {example.max_dok}"))
    if example.conceptual:
        notes.append(_t("conceptual_note"))
    return tuple(notes)


def _exercise_notes(prep: PeriodPrep, exercises: Sequence[int]) -> tuple[str, ...]:
    out = []
    for x in exercises:
        dok = next((d for e in prep.practice_examples if (d := e.dok_of(x)) is not None), None)
        if dok is not None:
            ref = book_ref("التمرين", x, prep.exercise_pages.get(x))
            out.append(_t("exercise_depth_note", ref=ref, dok=dok))
    return tuple(out)


def item_bullets(item) -> tuple[str, ...]:
    """السؤال وخياراته الأربعة (أ-د) على الشريحة؛ المفتاح ونوع الخطأ في الملاحظات وحدها."""
    return (
        isolate_outside_math(item.stem),
        *(isolate_outside_math(f"{OPTION_LETTERS[i]}) {o.text}") for i, o in enumerate(item.options)),
    )


def item_notes(item) -> tuple[str, ...]:
    """جانب المعلم: مفتاح الإجابة، وسوء الفهم الذي يكشفه كل خيار خاطئ، وخطوة «اختر ثم برّر» بقيدها الفردي."""
    notes = [_t("answer_note", letter=OPTION_LETTERS[item.answer_index])]
    for i, option in enumerate(item.options):
        if not option.correct:
            notes.append(_t("distractor_note", letter=OPTION_LETTERS[i], misconception=option.misconception))
    notes.append(_t("choose_justify_note"))
    return tuple(notes)


def _open_texts(
    prep: PeriodPrep, n: int, question: OpenQuestion | None
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(بنود السؤال على الشريحة، ملاحظاته): سؤال مقالي بإجابته، وإلا تمرين الكتاب برقمه وصفحته، وإلا مرجع المثال."""
    ref = book_ref("المثال", n, prep.pages.get(n))
    if question is not None:
        parts = tuple(isolate_outside_math(part) for part in split_stem(question.problem.stem))
        answer = isolate_number_ranges(plain_math(question.problem.answer))
        return parts, (_t("open_note", ref=ref, answer=answer),)
    number = book_exercise(prep, n)
    if number is None:
        return (_t("skill_question", ref=ref),), ()
    exercise = book_ref("التمرين", number, prep.exercise_pages.get(number))
    return (_t("book_question", exercise=exercise, ref=ref),), (_t("book_note", exercise=exercise),)


def _slide(kind: str, title: str, **fields) -> PeriodSlide:
    return PeriodSlide(kind=kind, phase=SLIDE_PHASE[kind], title=title, **fields)


def _draft_slides(
    prep: PeriodPrep,
    groups: dict[int, tuple[ExampleClip, ...]],
    practice: dict[int, tuple[ExampleClip, ...]] | None = None,
    items: PeriodItems | None = None,
) -> list[PeriodSlide]:
    """الشرائح بترتيب المراحل بلا دقائق: العنوان والاستدعاء، الأهداف، ولكل مثال مقاطعه وتدريبه الصفي، ثم الممارسة
    المستقلة والفحص وبطاقة الخروج واختبار الدرس والواجب."""
    bullets = [_t("period", k=prep.k, n=prep.n)]
    if prep.standards:
        bullets.append(_t("standards", codes="، ".join(prep.standards)))
    pages = sorted({e.page for e in prep.examples if e.page})
    if pages:
        bullets.append(_t("book_pages", pages=number_list(pages)))
    items = items or period_items(prep)
    recall_text = isolate_number_ranges(recall_label(prep.recall))
    recalls = [
        _slide(
            "recall",
            _t("recall_title"),
            bullets=item_bullets(item),
            notes=(*((recall_text,) if i == 0 else ()), *item_notes(item)),
        )
        for i, item in enumerate(items.warmup)
    ] or [_slide("recall", _t("recall_title"), bullets=(recall_text,))]
    if prep.lesson_title:
        bullets.insert(0, isolate_number_ranges(prep.lesson_title))
    slides = [_slide("title", _t("title", lesson=prep.lesson), bullets=tuple(bullets)), *recalls]
    terms = [_t("term", ar=ar, en=en) if en else ar for ar, en in prep.terms]
    if prep.objectives:
        notes = tuple(
            _t(
                "objective_note",
                ref=book_ref("مثال", o.example, prep.pages.get(o.example)),
                condition=o.condition,
                criterion=o.criterion,
            )
            for o in prep.objectives
            if o.condition and o.criterion
        )
        slides.append(
            _slide(
                "objectives",
                _t("objectives_title"),
                bullets=tuple(objective_bullet(prep, i) for i in range(len(prep.objectives))),
                refs=tuple(o.example for o in prep.objectives),
                notes=notes,
            )
        )
    for start in range(0, len(terms), MAX_BULLETS):
        chunk = tuple(terms[start : start + MAX_BULLETS])
        slides.append(_slide("terms", _t("terms_title"), bullets=chunk))
    classwork = {c.example: c for c in prep.classwork}
    for e in prep.examples:
        clips = groups[e.n]
        for clip in clips:
            title = example_title("example" if clip.part == 1 else "continued", e)
            notes = _period_example_notes(e) if clip.part == 1 else ()
            slides.append(_slide("example", title, refs=(e.n,), clip=clip, alt=example_alt(e), notes=notes))
        for clip in (practice or {}).get(e.n, ()):
            name = "try_title" if clip.part == 1 else "try_continued_title"
            title = _t(name, ref=book_ref("مثال", e.n, e.page))
            slides.append(_slide("try", title, refs=(e.n,), clip=clip, alt=try_alt(e)))
        if e.n in classwork:
            exercises = classwork[e.n].exercises
            slides.append(
                _slide(
                    "classwork",
                    _t("classwork_title", ref=book_ref("مثال", e.n, e.page)),
                    bullets=(
                        _t("exercises", numbers=numbers_with_pages(list(exercises), prep.exercise_pages)),
                    ),
                    refs=(e.n,),
                    notes=_exercise_notes(prep, exercises),
                )
            )
    if prep.basic or prep.advanced:
        paths = []
        if prep.basic:
            paths.append(_t("basic", numbers=numbers_with_pages(list(prep.basic), prep.exercise_pages)))
        if prep.advanced:
            paths.append(_t("advanced", numbers=numbers_with_pages(list(prep.advanced), prep.exercise_pages)))
        notes = (_t("differentiation_note"), *_exercise_notes(prep, [*prep.basic, *prep.advanced]))
        slides.append(_slide("differentiation", _t("independent_title"), bullets=tuple(paths), notes=notes))
    with_item, as_open = split_check_questions(prep, items)
    for n in with_item:
        slides.append(
            _slide(
                "check",
                _t("check_title"),
                bullets=item_bullets(items.formative[n]),
                refs=(n,),
                notes=item_notes(items.formative[n]),
            )
        )
    if as_open:
        questions, notes = [], []
        for n in as_open:
            parts, note = _open_texts(prep, n, items.open.get(n))
            questions.extend(parts)
            notes.extend(note)
        slides.append(
            _slide("check", _t("check_title"), bullets=tuple(questions), refs=as_open, notes=tuple(notes))
        )
    if prep.exit_ticket:
        n, dok = prep.exit_ticket.example, prep.exit_ticket.dok
        depth = _t("depth_note", depths=f"DOK {dok}")
        if items.exit is None:
            parts, note = _open_texts(prep, n, items.exit_open)
            slides.append(_slide("exit", _t("exit_title"), bullets=parts, refs=(n,), notes=(depth, *note)))
        else:
            slides.append(
                _slide(
                    "exit",
                    _t("exit_title"),
                    bullets=item_bullets(items.exit),
                    refs=(n,),
                    notes=(depth, *item_notes(items.exit)),
                )
            )
    if prep.quiz:
        counts = Counter(prep.quiz)
        depths = "، ".join(f"DOK {d} × {counts[d]}" for d in sorted(counts))
        slides.append(
            _slide(
                "quiz",
                _t("quiz_title"),
                bullets=(_t("quiz_count", count=len(prep.quiz)),),
                notes=(_t("quiz_note", depths=depths),),
            )
        )
    if prep.homework:
        slides.append(
            _slide(
                "homework",
                _t("homework_title"),
                bullets=(
                    _t("exercises", numbers=numbers_with_pages(list(prep.homework), prep.exercise_pages)),
                ),
                notes=_exercise_notes(prep, prep.homework),
            )
        )
    return slides


def _timed(prep: PeriodPrep, slides: Sequence[PeriodSlide]) -> tuple[PeriodSlide, ...]:
    """دقائق كل مرحلة تتوزع على شرائحها، وتُكتب مع اسم الطور أولَ ملاحظات المتحدث."""
    shares = {
        stage.name: split_minutes(stage.minutes, sum(1 for s in slides if s.phase == stage.name))
        for stage in prep.stages
    }
    out = []
    for s in slides:
        if s.phase not in shares:
            raise DeckError(f"مرحلة {s.phase} ليست في التحضير")
        m = shares[s.phase].pop(0)
        head = (_t("phase_note", phase=STAGE_LABELS[s.phase]), _t("minutes_note", minutes=m))
        out.append(replace(s, minutes=m, notes=(*head, *s.notes)))
    return tuple(out)


def build_period_deck(
    prep: PeriodPrep, clips: Sequence[ExampleClip], shown: Sequence[ExampleClip] | None = None
) -> PeriodDeck:
    """عرض الحصة من تحضيرها ومقاطع أمثلتها. مقطع لمثال خارج الحصة، أو مثال بلا مقطع، أو أجزاء غير متصلة: خطأ لا تخمين.

    `shown` المقاطع كما تُرسم حين تخالف المصدر (تتمة قصيرة ضُمّت إلى ما قبلها في طبقة المقاطع): الشرائح منها، والمفتاح
    من `clips` المصدر دائمًا فيبقى محسوبًا من فهرس الأصول وحده."""
    groups = _clip_groups(prep, [c for c in clips if c.kind == "example"])
    if shown is not None:
        groups = _clip_groups(prep, [c for c in shown if c.kind == "example"])
    drawn = clips if shown is None else shown
    practice = _practice_groups(prep, [c for c in drawn if c.kind == "practice"])
    slides = _timed(prep, _draft_slides(prep, groups, practice, period_items(prep)))
    return PeriodDeck(
        key=period_deck_key(prep, clips),
        course=prep.course,
        lesson=prep.lesson,
        k=prep.k,
        n=prep.n,
        minutes=prep.minutes,
        slides=slides,
    )
