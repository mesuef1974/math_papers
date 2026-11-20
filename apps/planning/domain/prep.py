"""تحضير حصة الدرس: اشتقاق حتمي من الفهرس المشتق والخطة الفصلية ومكتبة الاستراتيجيات، بلا Django ولا نص دليل.

`allocate` يوزّع أمثلة الدرس الأساسية على حصصه، و`build_prep` يبني تحضير حصة واحدة (`PeriodPrep`): أمثلتها وأهدافها
وتدريباتها وتقويمها وربطها بما قبلها ومراحلها الست بأزمنتها. كل حقل نصي فيه رمز أو فئة مغلقة أو معرّف من مكتبتنا؛ نصوص
الأهداف من ملف الوحدة المؤلَّف (`prep/unit-<n>.json`، `knowledge.domain.unit_prep`) بمصدر «مؤلَّف»، وغيابها حالة «معلَّق»
لا فشل (`prep_checks`). التصميم والمعايير: `docs/lesson_prep_plan.md`.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field

from apps.knowledge.domain.course_index import LessonIndex
from apps.knowledge.domain.exercise_pages import page_map
from apps.knowledge.domain.unit_prep import AuthoredObjective

from .calendar_engine import PlanningError
from .strategies import Strategy, distribute

# ---- الإعداد: أرقام التصميم في مكان واحد (تُراجع بعد أول تجربة في الصف؛ الزمن والمراحل والسقف قرار المالك) ----
PERIOD_MINUTES = 45
MAX_OBJECTIVES = 3
CLASSWORK_PER_EXAMPLE = 2
DIFFERENTIATION_SIZE = 3
BASIC_MAX_DOK = 2  # بلا دليل مهام: مسار الأساسي من أمثلة بهذا العمق فأقل (`derived_paths`)
HOMEWORK_RANGE = (3, 8)

# المراحل الست للإفلات التدريجي: (المرحلة، الزمن الافتراضي، الحد الأدنى، الحد الأعلى، أطوار المكتبة التي تُختار منها)
STAGES: tuple[tuple[str, int, int, int, tuple[str, ...]], ...] = (
    ("warmup", 5, 3, 7, ("opening",)),
    ("objectives", 2, 1, 3, ()),
    ("direct", 12, 8, 16, ("explain",)),
    ("guided", 10, 6, 14, ("explore",)),
    ("independent", 11, 5, 15, ("practice",)),
    ("closing", 5, 3, 7, ("close",)),
)
STAGE_NAMES = tuple(s[0] for s in STAGES)
STAGE_BOUNDS = {s[0]: (s[2], s[3]) for s in STAGES}
# عمق أعلى: تعليم مباشر وممارسة موجهة أطول على حساب المستقلة، والمجموع ثابت
DEPTH_SHIFT = {1: 0, 2: 0, 3: 1, 4: 2}

# أفعال الأهداف بعمق DOK (بصياغتنا)، والمرفوضة لأنها لا تُقاس
VERBS_BY_DOK: dict[int, tuple[str, ...]] = {
    1: ("يحسب", "يحدد", "يسمّي", "يقرأ", "يكتب"),
    2: ("يحل", "يمثّل", "يقارن", "يصنّف", "يفسّر"),
    3: ("يحلل", "يبرر", "يستنتج", "ينمذج", "يقيّم"),
    4: ("يصمّم", "يبرهن", "ينشئ", "يقيّم"),
}
REJECTED_VERBS = frozenset({"يفهم", "يعرف", "يدرك", "يتعرّف", "يتعرف"})

# مصادر الحقول المشتقة
SOURCES = frozenset({"plan", "index", "library", "generator", "authored", "teacher"})

# أمثلة مفاهيمية (اشتقاق قانون): لها هدف ومقطع، ولا تدريب لها ولا سؤال خروج (قرار المالك 2026-11-19)
CONCEPTUAL_EXAMPLES: dict[str, dict[str, frozenset[int]]] = {"g10-s1": {"2.6": frozenset({1})}}

RECALL_KINDS = frozenset({"previous_lesson", "previous_period", "exit_review", "prior_knowledge"})


class PrepError(PlanningError):
    """لا تحضير ممكن بهذه المدخلات."""


@dataclass(frozen=True)
class TeacherEdit:
    """تعديل المعلم لحصة واحدة كما يدخل الاشتقاق: `allocation` صادقة حين يخالف توزيعه توزيع `allocate` (للمصدر وحده؛
    التوزيع نفسه في `groups`)، و`strategies` المرحلة → معرّف استراتيجية، و`removed` تمارين لا تدخل أي تدريب في الحصة."""

    allocation: bool = False
    strategies: Mapping[str, str] = field(default_factory=dict)
    removed: frozenset[int] = frozenset()


@dataclass(frozen=True)
class PrepExample:
    n: int
    page: int | None
    representations: tuple[str, ...]
    rows: tuple[tuple[int, tuple[int, ...]], ...]  # صفوف التحليل: (العمق، التمارين)
    weight: int
    conceptual: bool = False
    extension: bool = False  # مثال إثرائي أُدرج امتدادًا معلَّمًا
    # عدد شرائح مقاطع المثال: الأصل وتتماته، والتتمة القصيرة المضمومة إلى ما قبلها لا تُعدّ؛ None: لم تُعرف الأصول بعد
    continuations: int | None = None
    has_generator: bool = False
    # صفوف تمارين قسم «تمارين» للمثال (`kind: practice`): للتمايز والواجب في درس بلا دليل مهام، لا للتدريب الصفي ولا للوزن
    practice: tuple[tuple[int, tuple[int, ...]], ...] = ()

    @property
    def max_dok(self) -> int:
        return max((d for d, _ in (*self.rows, *self.practice)), default=0)

    def dok_of(self, exercise: int) -> int | None:
        return next((d for d, ex in (*self.rows, *self.practice) if exercise in ex), None)


@dataclass(frozen=True)
class Objective:
    """هدف إجرائي لمثال بصيغة ABCD. الأجزاء الأربعة None حتى يصل ملف الوحدة المعتمد (معلَّق)."""

    example: int
    dok: int
    verb: str
    audience: str | None = None
    behavior: str | None = None
    condition: str | None = None
    criterion: str | None = None
    source: str = "index"

    @property
    def parts(self) -> tuple[str | None, ...]:
        return (self.audience, self.behavior, self.condition, self.criterion)


@dataclass(frozen=True)
class Classwork:
    example: int
    dok: int
    exercises: tuple[int, ...]


@dataclass(frozen=True)
class ExitTicket:
    example: int
    dok: int


@dataclass(frozen=True)
class Recall:
    kind: str
    lesson: str | None = None
    k: int | None = None


@dataclass(frozen=True)
class Stage:
    name: str
    minutes: int
    strategy: str | None  # معرّف من المكتبة
    bounds: tuple[int, int]  # تقاطع حدّي المرحلة وحدّي استراتيجيتها


@dataclass(frozen=True)
class PeriodPrep:
    course: str
    lesson: str
    unit: int
    k: int
    n: int
    minutes: int
    kind: str
    examples: tuple[PrepExample, ...]  # أمثلة الحصة الجديدة (فارغة في الحصة الأخيرة)
    review: tuple[PrepExample, ...]  # أمثلة الدرس كلها للحصة الأخيرة: التمايز والتقويم عليها
    objectives: tuple[Objective, ...]
    standards: tuple[str, ...]
    practices: tuple[str, ...]
    classwork: tuple[Classwork, ...]
    basic: tuple[int, ...]
    advanced: tuple[int, ...]
    homework: tuple[int, ...]
    formative: tuple[int, ...]  # أمثلة يقيس الفحص التكويني مهاراتها (لها مولّد)
    exit_ticket: ExitTicket | None
    quiz: tuple[int, ...]  # أعماق اختبار الدرس في الحصة الأخيرة
    recall: Recall
    stages: tuple[Stage, ...]
    task_guide: tuple[frozenset[int], frozenset[int]] = (frozenset(), frozenset())
    unit_status: str | None = None  # حالة ملف الوحدة: None (لم يُولَّد) أو draft أو approved
    sources: Mapping[str, str] = field(default_factory=dict)
    # صفحة كل تمرين في الحصة (الصفي والمساران والواجب) في كتاب الطالب حين تُعرف؛ الفارغ خارج التجزئة
    exercise_pages: Mapping[int, int] = field(default_factory=dict)

    @property
    def practice_examples(self) -> tuple[PrepExample, ...]:
        """الأمثلة التي تُستمد منها تدريبات الحصة: أمثلتها، وفي الأخيرة أمثلة الدرس كلها."""
        return self.examples or self.review

    @property
    def is_last(self) -> bool:
        return self.k == self.n


def prep_digest(prep: PeriodPrep) -> str:
    """تجزئة ثابتة لكل حقول التحضير (المجموعات مرتبة): تغيّر أي حقل يغيّرها فيُعلَّم عرضه قديمًا.

    `practice` الفارغ في المثال و`exercise_pages` الفارغ خارج التجزئة: دخول الحقل لا يعلّم عروض مقرر بلا قيمه قديمةً."""

    def plain(value: object) -> object:
        if isinstance(value, (set, frozenset)):
            return sorted(value)
        raise TypeError(type(value).__name__)

    payload = asdict(prep)
    for example in (*payload["examples"], *payload["review"]):
        if not example["practice"]:
            del example["practice"]
    if not payload["exercise_pages"]:
        del payload["exercise_pages"]
    data = json.dumps(payload, default=plain, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def parse_ranges(text: str) -> frozenset[int]:
    """«10-21, 23, 25–31» (شرطة أو شرطة طويلة، ومسافات حرة) → مجموعة الأرقام."""
    numbers: set[int] = set()
    for part in re.split(r"\s*[,،]\s*", text.strip()):
        if not part:
            continue
        bounds = re.split(r"\s*[-–]\s*", part)
        lo, hi = int(bounds[0]), int(bounds[-1])
        numbers.update(range(lo, hi + 1))
    return frozenset(numbers)


def example_weight(rows: Iterable[tuple[int, Sequence[int]]], continuations: int | None) -> int:
    """وزن المثال: مجموع أعماق صفوف تحليله وعدد تتماته (المقطع الأول ليس تتمة)."""
    return sum(d for d, _ in rows) + max((continuations or 0) - 1, 0)


def allocate(weights: Sequence[tuple[int, int]], n: int) -> tuple[tuple[int, ...], ...]:
    """يوزّع الأمثلة (رقمها ووزنها، بترتيبها) على `n` حصص: الأخيرة بلا مثال، وكل حصة قبلها من مثال إلى ثلاثة متتالية.

    الاختيار: أصغر أثقل حصة، ثم أصغر فرق بين الأثقل والأخف، ثم أكبر الحصص أولًا؛ فالنتيجة حتمية.
    """
    slots = n - 1
    count = len(weights)
    if slots < 1:
        raise PrepError(f"درس بحصة واحدة لا يتسع لأمثلة وتقويم: {n}")
    if not slots <= count <= MAX_OBJECTIVES * slots:
        raise PrepError(f"{count} أمثلة لا تتوزع على {slots} حصص بمثال إلى {MAX_OBJECTIVES} لكل حصة")
    best: tuple[tuple[int, int, tuple[int, ...]], tuple[int, ...]] | None = None
    for sizes in itertools.product(range(1, MAX_OBJECTIVES + 1), repeat=slots):
        if sum(sizes) != count:
            continue
        loads, start = [], 0
        for size in sizes:
            loads.append(sum(w for _, w in weights[start : start + size]))
            start += size
        key = (max(loads), max(loads) - min(loads), tuple(-s for s in sizes))
        if best is None or key < best[0]:
            best = (key, sizes)
    assert best is not None
    groups, start = [], 0
    for size in best[1]:
        groups.append(tuple(n for n, _ in weights[start : start + size]))
        start += size
    return (*groups, ())


def lesson_examples(
    lesson: LessonIndex,
    course: str,
    enrichment: Iterable[int] = (),
    generators: Iterable[int] = (),
    clips: Mapping[int, int] | None = None,
    slides: Mapping[int, int] | None = None,
) -> tuple[PrepExample, ...]:
    """أمثلة الدرس الأساسية (بلا الإثرائي) بصفوف تحليلها وأوزانها.

    `clips` عدد مقاطع كل مثال في الكتاب (الأصل وتتماته) ومنه الوزن، و`slides` عدد شرائحها بعد ضمّ التتمات القصيرة (بلا
    `slides` لكل مقطع شريحة): الضمّ يغيّر العرض لا حجم المثال، فلا يغيّر توزيع الأمثلة على الحصص."""
    skip, gens = set(enrichment), set(generators)
    conceptual = CONCEPTUAL_EXAMPLES.get(course, {}).get(lesson.lesson, frozenset())
    rows: dict[int, list[tuple[int, tuple[int, ...]]]] = {}
    extra: dict[int, list[tuple[int, tuple[int, ...]]]] = {}
    for row in lesson.analysis:
        target = extra if row.kind == "practice" else rows
        target.setdefault(row.example, []).append((row.dok, tuple(row.exercises)))
    out = []
    for e in lesson.examples:
        if e.n in skip:
            continue
        own = tuple(sorted(rows.get(e.n, ())))
        parts = None if clips is None else clips.get(e.n, 0)
        continuations = parts if parts is None or slides is None else slides.get(e.n, 0)
        out.append(
            PrepExample(
                n=e.n,
                page=e.page,
                representations=tuple(e.representations),
                rows=own,
                weight=example_weight(own, parts),
                conceptual=e.n in conceptual,
                continuations=continuations,
                has_generator=e.n in gens,
                practice=tuple(sorted(extra.get(e.n, ()))),
            )
        )
    return tuple(out)


def _classwork(
    examples: Sequence[PrepExample], removed: frozenset[int] = frozenset()
) -> tuple[Classwork, ...]:
    """تدريب صفي لكل مثال (غير مفاهيمي) من صف تحليله الأقل عمقًا بلا ما حذفه المعلم، مرتبًا بالعمق فرقم المثال: التدرج من
    الأسهل. المثال الذي حُذفت تمارين صفه كلها بلا تدريب صفي، فيفشل T4 ولا يُحفظ التعديل."""
    out = []
    for e in examples:
        if e.conceptual or not e.rows:
            continue
        dok, exercises = min(e.rows)
        kept = tuple(x for x in exercises if x not in removed)
        if kept:
            out.append(Classwork(e.n, dok, kept[:CLASSWORK_PER_EXAMPLE]))
    return tuple(sorted(out, key=lambda c: (c.dok, c.example)))


def _exercises_by_depth(
    examples: Sequence[PrepExample], practice_only: bool = False
) -> list[tuple[int, int]]:
    """(العمق، التمرين) لكل تمرين في صفوف أمثلة الحصة (أو صفوف `practice` وحدها)، مرتبة بالعمق فالرقم."""
    return sorted(
        {
            (d, x)
            for e in examples
            for d, ex in (e.practice if practice_only else (*e.rows, *e.practice))
            for x in ex
        }
    )


def derived_paths(
    lesson: Sequence[PrepExample], period: Sequence[PrepExample]
) -> tuple[frozenset[int], frozenset[int]]:
    """مسارا الأساسي والمتقدم في حصة درس بلا دليل مهام، من أعماق الأمثلة (قرار المالك 2026-11-20): الأساسي تمارين
    `practice` لأمثلة الحصة التي عمقها 1 أو 2، والمتقدم تمارين `practice` لأمثلتها التي بأعلى عمق في الدرس (بين أمثلته
    التي لها صفوف `practice`). الحصة التي لا مثال فيها بالشرط تأخذ أقرب أمثلتها إليه: الأدنى عمقًا للأساسي والأعلى للمتقدم،
    فلا تفرغ قائمة وللحصة تمارين."""
    own = [e for e in period if e.practice]
    top = max((e.max_dok for e in lesson if e.practice), default=0)
    lowest = min((e.max_dok for e in own), default=0)
    highest = max((e.max_dok for e in own), default=0)

    def numbers(chosen: Sequence[PrepExample], fallback: int) -> frozenset[int]:
        chosen = chosen or [e for e in own if e.max_dok == fallback]
        return frozenset(x for e in chosen for _, ex in e.practice for x in ex)

    return (
        numbers([e for e in own if e.max_dok <= BASIC_MAX_DOK], lowest),
        numbers([e for e in own if e.max_dok == top], highest),
    )


def stage_options(library: Iterable[Strategy], name: str) -> tuple[Strategy, ...]:
    """الاستراتيجيات الصالحة لمرحلة: من أطوارها، بلا موارد، وحدّاها يتقاطعان مع حدّي المرحلة. مصدر واحد للاشتقاق وتعديل المعلم."""
    _, _, lo, hi, phases = next(s for s in STAGES if s[0] == name)
    return tuple(s for s in library if s.phase in phases and not s.needs and max(s.min, lo) <= min(s.max, hi))


def _stages(
    library: Sequence[Strategy],
    dok: frozenset[int],
    max_dok: int,
    minutes: int = PERIOD_MINUTES,
    chosen_by_teacher: Mapping[str, str] | None = None,
) -> tuple[Stage, ...]:
    """المراحل الست: لكل مرحلة أنسب استراتيجية بلا موارد لعمق الحصة (أو ما اختاره المعلم منها)، ثم الدقائق ضمن حدّي المرحلة
    واستراتيجيتها ومجموعها الزمن."""
    forced = chosen_by_teacher or {}
    shift = DEPTH_SHIFT.get(max_dok, 0)
    ideal: dict[str, float] = {}
    bounds: dict[str, tuple[int, int]] = {}
    chosen: dict[str, str | None] = {}
    for name, default, lo, hi, phases in STAGES:
        ideal[name] = default + {"direct": shift, "guided": shift, "independent": -2 * shift}.get(name, 0)
        strategy = None
        if phases:
            fits = stage_options(library, name)
            if not fits:
                raise PrepError(f"لا استراتيجية للمرحلة {name}")
            if name in forced:
                strategy = next((s for s in fits if s.slug == forced[name]), None)
                if strategy is None:
                    raise PrepError(f"الاستراتيجية {forced[name]} لا تصلح للمرحلة {name}")
            else:
                strategy = sorted(
                    fits,
                    key=lambda s: (-len(dok & set(s.dok)), not s.min <= ideal[name] <= s.max, s.slug),
                )[0]
            lo, hi = max(strategy.min, lo), min(strategy.max, hi)
        chosen[name] = strategy.slug if strategy else None
        bounds[name] = (lo, hi)
    split = distribute(ideal, bounds, minutes)
    if split is None:
        raise PrepError(f"لا توزيع لدقائق المراحل يساوي {minutes}")
    return tuple(Stage(name, split[name], chosen[name], bounds[name]) for name in STAGE_NAMES)


def lesson_quiz_depths(lesson: LessonIndex, examples: Sequence[PrepExample]) -> tuple[int, ...]:
    """أعماق اختبار الدرس: من دليله إن ذكرها، وإلا مشتقة من أمثلته (قرار المالك 2026-11-20 لكتاب بلا أعماق اختبار
    كالثاني عشر): سؤال لكل مثال غير إثرائي له صفوف تحليل، بأعلى عمق في صفوفه، بترتيب الأمثلة."""
    if lesson.quiz_depths:
        return tuple(lesson.quiz_depths)
    return tuple(e.max_dok for e in sorted(examples, key=lambda e: e.n) if e.rows and not e.extension)


def build_prep(
    *,
    course: str,
    lesson: LessonIndex,
    examples: Sequence[PrepExample],
    groups: Sequence[Sequence[int]],
    k: int,
    recall: Recall,
    library: Sequence[Strategy],
    unit_status: str | None = None,
    authored: Mapping[int, AuthoredObjective] | None = None,
    audience: str | None = None,
    teacher: TeacherEdit | None = None,
) -> PeriodPrep:
    """تحضير الحصة `k` من حصص الدرس (`groups` من `allocate` أو توزيع المعلم): مشتق كله من مدخلاته، فالمدخل نفسه يعطي
    التحضير نفسه. `teacher` تعديل المعلم لهذه الحصة: استراتيجيات اختارها لمراحل وتمارين حذفها من كل تدريبات الحصة."""
    edit = teacher or TeacherEdit()
    n = len(groups)
    if not 1 <= k <= n:
        raise PrepError(f"الحصة {k} خارج حصص الدرس {n}")
    by_n = {e.n: e for e in examples}
    own = tuple(by_n[x] for x in groups[k - 1])
    last = k == n
    review = tuple(examples) if last else ()
    practice = own or review
    guide = lesson.task_guide
    # بلا دليل مهام المساران مشتقان من أعماق أمثلة الدرس، والتمايز والواجب من صفوف `practice` وحدها
    basic_path, advanced_path = (
        (parse_ranges(guide.basic), parse_ranges(guide.advanced))
        if guide
        else derived_paths(examples, practice)
    )

    classwork = _classwork(own, edit.removed) if own else ()
    taken = {x for c in classwork for x in c.exercises}
    pool = [
        (d, x)
        for d, x in _exercises_by_depth(practice, practice_only=guide is None)
        if x not in taken and x not in edit.removed
    ]
    basic = tuple(x for _, x in [p for p in pool if p[1] in basic_path][:DIFFERENTIATION_SIZE])
    # المساران المشتقان يتقاطعان حين يكون أعلى عمق 2 فأقل أو للحصة مثال واحد: المتقدم يقدّم ما لم يأخذه الأساسي
    advanced = tuple(
        x
        for _, x in sorted(
            [p for p in pool if p[1] in advanced_path],
            key=lambda p: (guide is None and p[1] in basic, -p[0], p[1]),
        )[:DIFFERENTIATION_SIZE]
    )
    if guide:
        # الواجب: الباقي من تمارين أمثلة الحصة في مسار الطالب (الأساسي) بعد التدريب الصفي وقائمة الدعم
        rest = {x for _, x in pool if x in basic_path and x not in basic}
    else:
        rest = {x for _, x in pool if x not in basic and x not in advanced}
    homework = tuple(sorted(rest)[: HOMEWORK_RANGE[1]])

    measurable = tuple(e.n for e in practice if e.has_generator and not e.conceptual)
    exit_ticket = None
    if not last:
        for c in reversed(classwork):
            if by_n[c.example].has_generator:
                exit_ticket = ExitTicket(c.example, c.dok)
                break

    written = authored or {}
    objectives = tuple(_objective(e, written.get(e.n), audience) for e in own)
    depths = frozenset(d for e in practice for d, _ in (*e.rows, *e.practice))
    return PeriodPrep(
        course=course,
        lesson=lesson.lesson,
        unit=lesson.unit,
        k=k,
        n=n,
        minutes=PERIOD_MINUTES,
        kind="lesson",
        examples=own,
        review=review,
        objectives=objectives,
        standards=tuple(lesson.standards),
        practices=tuple(lesson.practices),
        classwork=classwork,
        basic=basic,
        advanced=advanced,
        homework=homework,
        formative=measurable,
        exit_ticket=exit_ticket,
        quiz=lesson_quiz_depths(lesson, examples) if last else (),
        recall=recall,
        stages=_stages(library, depths, max(depths, default=1), chosen_by_teacher=edit.strategies),
        task_guide=(basic_path, advanced_path),
        unit_status=unit_status,
        sources={
            "examples": "index",
            "allocation": "teacher" if edit.allocation else "plan",
            "objectives": "authored" if written else "index",
            "practice": "teacher" if edit.removed else "index",
            "assessment": "generator",
            "stages": "teacher" if edit.strategies else "library",
        },
        exercise_pages=_period_pages(
            lesson, (*(x for c in classwork for x in c.exercises), *basic, *advanced, *homework)
        ),
    )


def _period_pages(lesson: LessonIndex, exercises: Iterable[int]) -> dict[int, int]:
    pages = page_map(lesson.exercise_pages)
    return {x: pages[x] for x in sorted(set(exercises)) if x in pages}


def _objective(example: PrepExample, authored: AuthoredObjective | None, audience: str | None) -> Objective:
    """هدف المثال: من ملف الوحدة إن كُتب (بفعله وعمقه كما كُتبا، فيفحصهما T2)، وإلا عمق المثال وأول أفعاله بلا نص."""
    dok = max(example.max_dok, 1)
    if authored is None:
        return Objective(example=example.n, dok=dok, verb=VERBS_BY_DOK[dok][0])
    return Objective(
        example=example.n,
        dok=authored.dok,
        verb=authored.verb,
        audience=audience,
        behavior=authored.behavior,
        condition=authored.condition,
        criterion=authored.criterion,
        source="authored",
    )


def recall_for(k: int, previous_lesson: str | None, after_break: bool) -> Recall:
    """الربط بما قبلها: الأولى بالدرس السابق (أو المعرفة السابقة لأول درس)، وما بعدها بالحصة السابقة، وبعد انقطاع ببطاقة خروجها."""
    if k == 1:
        return Recall("previous_lesson", previous_lesson) if previous_lesson else Recall("prior_knowledge")
    return Recall("exit_review" if after_break else "previous_period", k=k - 1)
