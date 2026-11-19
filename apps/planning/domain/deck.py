"""نموذج عرض الدرس: شرائح حتمية من الفهرس المشتق وسير الحصة، بلا Django ولا نص دليل في المستودع.

نصوص الأهداف والمصطلحات وصور الأمثلة المقصوصة من الكتاب محتوى محميّ يبقى خارج المستودع (قاعدة نطاق المحتوى)؛ فهي مدخلات
`LessonContent` يمرّرها المعلم محليًا. ما يُشتق هنا فقط: ترتيب الشرائح، وتمثيلات كل مثال وعمق تمارينه من الفهرس، وسير الحصة
بدقائقه، وملخص اختبار الدرس. الناقص لا يُخمَّن: مدخل فارغ لا تُرسم له شريحة، ومثال مقصوص رقمه خارج الفهرس خطأ لا تجاهل.
التصدير في `pptx_export.py` وهو وحده يعرف شكل الملف.

عرض الحصة (`build_period_deck`، المرحلة 4 من `docs/lesson_prep_plan.md`) مدخله الوحيد تحضير حصة ومقاطع أمثلتها: لكل شريحة
مرحلتها من مراحل التحضير ودقائقها وملاحظات المتحدث، وكل نص فيها من قوالب `PERIOD_TEXT` أو من سلوك هدف مؤلَّف معتمد.
معاييره في `deck_checks.py`.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace

from apps.knowledge.domain.course_index import LessonIndex
from apps.papers.domain.bidi import isolate_number_ranges
from apps.papers.domain.book_source import number_list

from .calendar_engine import PlanningError
from .prep import PeriodPrep, PrepExample, prep_digest
from .prep_sheet import STAGE_LABELS, recall_label, split_minutes
from .strategies import Flow

PHASE_LABELS = {
    "opening": "التهيئة",
    "explore": "الاستكشاف",
    "explain": "الشرح",
    "practice": "التدريب",
    "check": "الفحص",
    "close": "الإغلاق",
}
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

    def __post_init__(self) -> None:
        if self.part < 1:
            raise DeckError(f"جزء المثال {self.n} غير صالح")
        if self.width_px <= 0 or self.height_px <= 0:
            raise DeckError(f"أبعاد صورة المثال {self.n} غير صالحة")
        if not self.png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise DeckError(f"صورة المثال {self.n} ليست PNG")


@dataclass(frozen=True)
class LessonContent:
    """ما يضعه المعلم من نصوصه المحلية: عنوان الدرس وأهدافه ومصطلحاته (عربي، إنجليزي) والأمثلة المقصوصة."""

    title: str
    objectives: tuple[str, ...] = ()
    vocabulary: tuple[tuple[str, str], ...] = ()
    examples: tuple[ExampleClip, ...] = ()


@dataclass(frozen=True)
class TitleSlide:
    title: str
    subtitle: str


@dataclass(frozen=True)
class BulletsSlide:
    title: str
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class TableSlide:
    title: str
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    footnote: str = ""


@dataclass(frozen=True)
class ExampleSlide:
    title: str
    clip: ExampleClip
    notes: tuple[str, ...]


Slide = TitleSlide | BulletsSlide | TableSlide | ExampleSlide


@dataclass(frozen=True)
class Deck:
    lesson: str
    slides: tuple[Slide, ...]


def _example_notes(lesson: LessonIndex, n: int) -> tuple[str, ...]:
    indexed = next((e for e in lesson.examples if e.n == n), None)
    if indexed is None:
        raise DeckError(f"المثال {n} غير موجود في الدرس {lesson.lesson} بالفهرس")
    notes: list[str] = []
    if indexed.representations:
        notes.append(
            "التمثيلات: " + "، ".join(REPRESENTATION_LABELS.get(r, r) for r in indexed.representations)
        )
    doks = sorted({row.dok for row in lesson.analysis if row.example == n})
    if doks:
        notes.append("عمق التمارين المرتبطة: " + "، ".join(f"DOK {d}" for d in doks))
    return tuple(notes)


def _flow_slide(flow: Flow) -> TableSlide:
    rows = tuple((PHASE_LABELS[s.phase], s.strategy.title, f"{s.minutes}", f"{s.start}") for s in flow.steps)
    return TableSlide(
        title="سير الحصة",
        header=("الطور", "الاستراتيجية", "الدقائق", "يبدأ عند الدقيقة"),
        rows=rows,
        footnote=f"زمن الحصة {flow.period_minutes} دقيقة",
    )


def _assessment_slide(lesson: LessonIndex) -> TableSlide | None:
    if not lesson.quiz_depths:
        return None
    counts = Counter(lesson.quiz_depths)
    rows = tuple((f"DOK {d}", f"{counts[d]}") for d in sorted(counts))
    return TableSlide(
        title="التقويم",
        header=("العمق المعرفي", "عدد أسئلة اختبار الدرس"),
        rows=rows,
        footnote=f"عدد التمارين في الدرس {lesson.exercises_total}",
    )


def build_deck(lesson: LessonIndex, content: LessonContent, flow: Flow) -> Deck:
    """ترتيب الشرائح: العنوان، الأهداف، المصطلحات، مثال لكل مقصوص بترتيب رقمه وتتمته بعده، سير الحصة، التقويم."""
    if not content.title.strip():
        raise DeckError("عنوان الدرس فارغ")
    numbers = [(c.n, c.part) for c in content.examples]
    if len(set(numbers)) != len(numbers):
        raise DeckError("رقم مثال مكرر في المقصوصات")

    subtitle = f"الدرس {lesson.lesson}"
    if lesson.standards:
        subtitle += " · " + "، ".join(lesson.standards)
    slides: list[Slide] = [TitleSlide(content.title, subtitle)]
    if content.objectives:
        slides.append(BulletsSlide("أهداف الدرس", content.objectives))
    if content.vocabulary:
        slides.append(
            TableSlide("المصطلحات", ("المصطلح", "Term"), tuple((ar, en) for ar, en in content.vocabulary))
        )
    for clip in sorted(content.examples, key=lambda c: (c.n, c.part)):
        if clip.part == 1:
            slides.append(ExampleSlide(f"مثال {clip.n}", clip, _example_notes(lesson, clip.n)))
        else:
            _example_notes(lesson, clip.n)  # رقم خارج الفهرس خطأ حتى للتتمة
            slides.append(ExampleSlide(f"تابع المثال {clip.n}", clip, ()))
    slides.append(_flow_slide(flow))
    assessment = _assessment_slide(lesson)
    if assessment is not None:
        slides.append(assessment)
    return Deck(lesson.lesson, tuple(slides))


# ---- عرض الحصة من تحضيرها ----

# الإعداد: أرقام التصميم في مكان واحد (افتراضات تُراجع بعد أول تجربة في الصف)
PERIOD_DECK_FORMAT = 1
MINUTES_PER_SLIDE = 2
TITLE_PT, BODY_PT = 36, 28
MIN_TITLE_PT, MIN_BODY_PT = 32, 24
MAX_BULLETS = 6
MAX_LINES = 2
LINE_CHARS = 60  # حروف السطر بخط 24pt في منطقة محتوى 16:9 (تقدير محافظ)
MIN_CLIP_SHARE = 0.6  # S7: ارتفاع المقطع المعروض من ارتفاع منطقة المحتوى
MIN_CLIP_PPI = 150  # S7: بكسل المقطع لكل بوصة من مقاسه على الشريحة المعروضة بملء الشاشة
MIN_CONTRAST = 4.5  # S8: تباين النص وخلفيته

# لكل نوع شريحة مرحلته من مراحل التحضير
SLIDE_PHASE = {
    "title": "warmup",
    "recall": "warmup",
    "objectives": "objectives",
    "example": "direct",
    "reveal": "direct",
    "try": "guided",
    "classwork": "guided",
    "differentiation": "independent",
    "check": "closing",
    "exit": "closing",
    "quiz": "closing",
    "homework": "closing",
}
CLIP_KINDS = frozenset({"example", "reveal", "try"})

# قوالب كل نص في العرض (الشريحة والنص البديل والملاحظات)؛ S13 يقيس كلمات العرض بكلماتها
PERIOD_TEXT = {
    "title": "الدرس {lesson}",
    "period": "الحصة {k} من {n}",
    "standards": "المعايير: {codes}",
    "recall_title": "تذكّر",
    "objectives_title": "أهداف الحصة",
    "objective_pending": "مثال {n}: نص الهدف معلَّق",
    "objective_note": "مثال {n}: الشرط: {condition} · المعيار: {criterion}",
    "example_title": "مثال {n}",
    "continued_title": "تابع المثال {n}",
    "reveal_title": "حل المثال {n}",
    "try_title": "حاول أن تحل: مثال {n}",
    "alt": "مثال {n} من كتاب الطالب",
    "alt_page": "مثال {n} من كتاب الطالب، ص {page}",
    "classwork_title": "تدريب صفي: مثال {n}",
    "exercises": "حلّ تمارين الكتاب: {numbers}",
    "independent_title": "الممارسة المستقلة",
    "basic": "المسار الأساسي: تمارين الكتاب {numbers}",
    "advanced": "المسار المتقدم: تمارين الكتاب {numbers}",
    "check_title": "تحقّق من فهمك",
    "skill_question": "سؤال من مهارة المثال {n}",
    "exit_title": "بطاقة الخروج",
    "quiz_title": "اختبار الدرس",
    "quiz_count": "عدد الأسئلة {count}",
    "homework_title": "الواجب",
    "phase_note": "الطور: {phase}",
    "minutes_note": "الدقائق: {minutes}",
    "representations_note": "التمثيلات: {labels}",
    "depth_note": "عمق التمارين: {depths}",
    "exercise_depth_note": "التمرين {exercise}: DOK {dok}",
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
        return (self.title, *self.bullets, *((self.alt,) if self.alt else ()), *self.notes)


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


def period_deck_key(prep: PeriodPrep, clips: Sequence[ExampleClip]) -> str:
    """مفتاح ملف العرض: يشتق من تجزئة التحضير وتجزئة كل مقطع، فتغيّر أيهما يعطي مفتاحًا جديدًا."""
    digest = hashlib.sha256(f"{PERIOD_DECK_FORMAT}|{prep_digest(prep)}".encode())
    for clip in sorted(clips, key=lambda c: (c.n, c.part)):
        digest.update(f"|{clip.n}.{clip.part}:{hashlib.sha256(clip.png).hexdigest()}".encode())
    return f"decks/{prep.course}/{prep.lesson}-k{prep.k}of{prep.n}-p{prep.minutes}-{digest.hexdigest()[:16]}.pptx"


def objective_bullet(prep: PeriodPrep, index: int) -> str:
    """الهدف على الشريحة: سلوكه المعتمد بفعله (الشرط والمعيار في الملاحظات)، و«معلَّق» قبل اعتماد وحدته."""
    objective = prep.objectives[index]
    if prep.unit_status == "approved" and objective.behavior:
        return isolate_number_ranges(objective.behavior)
    return _t("objective_pending", n=objective.example)


def example_alt(example: PrepExample) -> str:
    return _t("alt_page", n=example.n, page=example.page) if example.page else _t("alt", n=example.n)


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


def _period_example_notes(example: PrepExample) -> tuple[str, ...]:
    notes = []
    if example.representations:
        labels = "، ".join(REPRESENTATION_LABELS.get(r, r) for r in example.representations)
        notes.append(_t("representations_note", labels=labels))
    depths = sorted({d for d, _ in example.rows})
    if depths:
        notes.append(_t("depth_note", depths="، ".join(f"DOK {d}" for d in depths)))
    if example.conceptual:
        notes.append(_t("conceptual_note"))
    return tuple(notes)


def _exercise_notes(prep: PeriodPrep, exercises: Sequence[int]) -> tuple[str, ...]:
    out = []
    for x in exercises:
        dok = next((d for e in prep.practice_examples if (d := e.dok_of(x)) is not None), None)
        if dok is not None:
            out.append(_t("exercise_depth_note", exercise=x, dok=dok))
    return tuple(out)


def _slide(kind: str, title: str, **fields) -> PeriodSlide:
    return PeriodSlide(kind=kind, phase=SLIDE_PHASE[kind], title=title, **fields)


def _draft_slides(prep: PeriodPrep, groups: dict[int, tuple[ExampleClip, ...]]) -> list[PeriodSlide]:
    """الشرائح بترتيب المراحل بلا دقائق: العنوان والاستدعاء، الأهداف، ولكل مثال مقاطعه وحله وتدريبه الصفي، ثم الممارسة
    المستقلة والفحص وبطاقة الخروج واختبار الدرس والواجب."""
    bullets = [_t("period", k=prep.k, n=prep.n)]
    if prep.standards:
        bullets.append(_t("standards", codes="، ".join(prep.standards)))
    slides = [
        _slide("title", _t("title", lesson=prep.lesson), bullets=tuple(bullets)),
        _slide("recall", _t("recall_title"), bullets=(isolate_number_ranges(recall_label(prep.recall)),)),
    ]
    if prep.objectives:
        notes = tuple(
            _t("objective_note", n=o.example, condition=o.condition, criterion=o.criterion)
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
    classwork = {c.example: c for c in prep.classwork}
    for e in prep.examples:
        clips = groups[e.n]
        for clip in clips:
            title = _t("example_title" if clip.part == 1 else "continued_title", n=e.n)
            notes = _period_example_notes(e) if clip.part == 1 else ()
            slides.append(_slide("example", title, refs=(e.n,), clip=clip, alt=example_alt(e), notes=notes))
        slides.append(
            _slide("reveal", _t("reveal_title", n=e.n), refs=(e.n,), clip=clips[-1], alt=example_alt(e))
        )
        if e.n in classwork:
            exercises = classwork[e.n].exercises
            slides.append(
                _slide(
                    "classwork",
                    _t("classwork_title", n=e.n),
                    bullets=(_t("exercises", numbers=number_list(list(exercises))),),
                    refs=(e.n,),
                    notes=_exercise_notes(prep, exercises),
                )
            )
    if prep.basic or prep.advanced:
        paths = []
        if prep.basic:
            paths.append(_t("basic", numbers=number_list(list(prep.basic))))
        if prep.advanced:
            paths.append(_t("advanced", numbers=number_list(list(prep.advanced))))
        notes = (_t("differentiation_note"), *_exercise_notes(prep, [*prep.basic, *prep.advanced]))
        slides.append(_slide("differentiation", _t("independent_title"), bullets=tuple(paths), notes=notes))
    if prep.formative:
        questions = tuple(_t("skill_question", n=n) for n in prep.formative)
        slides.append(_slide("check", _t("check_title"), bullets=questions, refs=prep.formative))
    if prep.exit_ticket:
        n, dok = prep.exit_ticket.example, prep.exit_ticket.dok
        notes = (_t("depth_note", depths=f"DOK {dok}"),)
        slides.append(
            _slide("exit", _t("exit_title"), bullets=(_t("skill_question", n=n),), refs=(n,), notes=notes)
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
                bullets=(_t("exercises", numbers=number_list(list(prep.homework))),),
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


def build_period_deck(prep: PeriodPrep, clips: Sequence[ExampleClip]) -> PeriodDeck:
    """عرض الحصة من تحضيرها ومقاطع أمثلتها. مقطع لمثال خارج الحصة، أو مثال بلا مقطع، أو أجزاء غير متصلة: خطأ لا تخمين."""
    slides = _timed(prep, _draft_slides(prep, _clip_groups(prep, clips)))
    return PeriodDeck(
        key=period_deck_key(prep, clips),
        course=prep.course,
        lesson=prep.lesson,
        k=prep.k,
        n=prep.n,
        minutes=prep.minutes,
        slides=slides,
    )
