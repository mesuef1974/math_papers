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
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import MISSING, Field, dataclass, field, fields, is_dataclass

from apps.knowledge.domain.course_index import LessonIndex
from apps.knowledge.domain.exercise_pages import page_map
from apps.knowledge.domain.unit_prep import AuthoredObjective

from .calendar_engine import PlanningError
from .strategies import LessonProfile, Strategy, distribute, score

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

# حقل أُضيف إلى التحضير بعد أن حُفظت بصمات (`prep_digest`): يُعلَّم بهذا فيخرج من البصمة ما دام بقيمته الافتراضية
DIGEST_OMITS_DEFAULT: Mapping[str, bool] = {"digest_omits_default": True}


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
    practice: tuple[tuple[int, tuple[int, ...]], ...] = field(default=(), metadata=DIGEST_OMITS_DEFAULT)

    @property
    def all_rows(self) -> tuple[tuple[int, tuple[int, ...]], ...]:
        """صفوف المثال كلها: `rows` (try) ثم `practice`. التدريب الصفي وبطاقة الخروج من `rows` وحدها."""
        return (*self.rows, *self.practice)

    @property
    def max_dok(self) -> int:
        return max((d for d, _ in self.all_rows), default=0)

    def dok_of(self, exercise: int) -> int | None:
        return next((d for d, ex in self.all_rows if exercise in ex), None)


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
    exercise_pages: Mapping[int, int] = field(default_factory=dict, metadata=DIGEST_OMITS_DEFAULT)
    # دروس المقرر قبل هذا الدرس بترتيبها، للحصة الأولى وحدها: مصدر بند الاسترجاع المتباعد؛ الفارغ خارج التجزئة
    earlier_lessons: tuple[str, ...] = field(default=(), metadata=DIGEST_OMITS_DEFAULT)
    # اسم الدرس من مقرره لغلاف العرض؛ الفارغ خارج التجزئة
    lesson_title: str = field(default="", metadata=DIGEST_OMITS_DEFAULT)

    @property
    def practice_examples(self) -> tuple[PrepExample, ...]:
        """الأمثلة التي تُستمد منها تدريبات الحصة: أمثلتها، وفي الأخيرة أمثلة الدرس كلها."""
        return self.examples or self.review

    @property
    def is_last(self) -> bool:
        return self.k == self.n


def prep_digest(prep: PeriodPrep) -> str:
    """تجزئة ثابتة لكل حقول التحضير (المجموعات مرتبة): تغيّر أي حقل يغيّرها فيُعلَّم عرضه قديمًا.

    الحقل المعلَّم بـ `DIGEST_OMITS_DEFAULT` خارج التجزئة ما دام بقيمته الافتراضية (في أي صنف من أصناف التحضير): دخول حقل
    جديد لا يغيّر البصمات المحفوظة قبله، فلا يُعلَّم عرض قديمًا بلا تغيّر في تحضيره."""

    def plain(value: object) -> object:
        if isinstance(value, (set, frozenset)):
            return sorted(value)
        raise TypeError(type(value).__name__)

    payload = _digest_payload(prep)
    data = json.dumps(payload, default=plain, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _digest_payload(value: object) -> object:
    """كـ `dataclasses.asdict` بلا الحقول المعلَّمة بـ `DIGEST_OMITS_DEFAULT` التي تساوي قيمتها الافتراضية."""
    if is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _digest_payload(getattr(value, f.name))
            for f in fields(value)
            if not (f.metadata.get("digest_omits_default") and getattr(value, f.name) == _default(f))
        }
    if isinstance(value, (list, tuple)):
        return [_digest_payload(v) for v in value]
    if isinstance(value, dict):
        return {k: _digest_payload(v) for k, v in value.items()}
    return value


def _default(spec: Field) -> object:
    return spec.default_factory() if spec.default_factory is not MISSING else spec.default


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
    """تدريب صفي لكل مثال (غير مفاهيمي) من صف تحليله الأقل عمقًا بلا ما حذفه المعلم ولا ما أخذه مثال قبله، مرتبًا بالعمق فرقم المثال: التدرج من
    الأسهل. المثال الذي حُذفت تمارين صفه كلها بلا تدريب صفي، فيفشل T4 ولا يُحفظ التعديل."""
    out = []
    taken: set[int] = set()
    for e in examples:
        if e.conceptual or not e.rows:
            continue
        rows = [(d, [x for x in ex if x not in removed]) for d, ex in sorted(e.rows)]
        # أول صف فيه تمرين لم يأخذه مثال قبله؛ وإلا (كل تمارينه مأخوذة) صفه الأقل عمقًا كما هو
        fresh = next(((d, kept) for d, ex in rows if (kept := [x for x in ex if x not in taken])), None)
        dok, kept = fresh or rows[0]
        if kept:
            out.append(Classwork(e.n, dok, tuple(kept[:CLASSWORK_PER_EXAMPLE])))
            taken.update(kept[:CLASSWORK_PER_EXAMPLE])
    return tuple(sorted(out, key=lambda c: (c.dok, c.example)))


def _exercises_by_depth(
    examples: Sequence[PrepExample], practice_only: bool = False
) -> list[tuple[int, int]]:
    """(العمق، التمرين) لكل تمرين في صفوف أمثلة الحصة (أو صفوف `practice` وحدها)، مرتبة بالعمق فالرقم."""
    return sorted(
        {(d, x) for e in examples for d, ex in (e.practice if practice_only else e.all_rows) for x in ex}
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


@dataclass(frozen=True)
class PracticeRules:
    """قواعد التمايز والواجب لحصة: مسارا الأساسي والمتقدم، ومن أي صفوف تُؤخذ التمارين، وما يبقى واجبًا."""

    paths: tuple[frozenset[int], frozenset[int]]
    practice_only: bool  # التمارين من صفوف `practice` وحدها
    homework: Callable[[int, Sequence[int], Sequence[int]], bool]  # (التمرين، الأساسي، المتقدم) → من الواجب؟


def practice_rules(
    lesson: LessonIndex, examples: Sequence[PrepExample], period: Sequence[PrepExample]
) -> PracticeRules:
    """مع دليل المهام: المساران منه، والتمارين من صفوف الأمثلة كلها، والواجب الباقي من مسار الطالب (الأساسي) بعد التدريب
    الصفي وقائمة الدعم. وبلا دليل: المساران مشتقان من أعماق أمثلة الدرس (`derived_paths`)، والتمارين من صفوف `practice`
    وحدها، والواجب ما لم تأخذه القائمتان."""
    guide = lesson.task_guide
    if guide:
        basic_path = parse_ranges(guide.basic)
        return PracticeRules(
            paths=(basic_path, parse_ranges(guide.advanced)),
            practice_only=False,
            homework=lambda x, basic, advanced: x in basic_path and x not in basic,
        )
    return PracticeRules(
        paths=derived_paths(examples, period),
        practice_only=True,
        homework=lambda x, basic, advanced: x not in basic and x not in advanced,
    )


def _differentiation(
    pool: Sequence[tuple[int, int]], rules: PracticeRules
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """المساران والواجب من `pool` ((العمق، التمرين) بعد التدريب الصفي) بلا تمرين مكرر بينها. المجمع الصغير يقصّر
    المسارين ليبقى للواجب نصيب؛ ولا يتكرر تمرين إلا حين لا يبقى لمسارٍ غيرُ ما أخذه الآخر (فلا يفرغ)."""
    size = min(DIFFERENTIATION_SIZE, max(1, (len({x for _, x in pool}) + 2) // 3))
    basic_path, advanced_path = rules.paths
    basic = tuple(x for _, x in pool if x in basic_path)[:size]
    hardest = [x for _, x in sorted(pool, key=lambda p: (-p[0], p[1])) if x in advanced_path]
    advanced = tuple([x for x in hardest if x not in basic] or hardest)[:size]
    used = {*basic, *advanced}
    rest = {x for _, x in pool if x not in used and rules.homework(x, basic, advanced)}
    return basic, advanced, tuple(sorted(rest)[: HOMEWORK_RANGE[1]])


def stage_options(library: Iterable[Strategy], name: str) -> tuple[Strategy, ...]:
    """الاستراتيجيات الصالحة لمرحلة: من أطوارها، بلا موارد، وحدّاها يتقاطعان مع حدّي المرحلة. مصدر واحد للاشتقاق وتعديل المعلم."""
    _, _, lo, hi, phases = next(s for s in STAGES if s[0] == name)
    return tuple(s for s in library if s.phase in phases and not s.needs and max(s.min, lo) <= min(s.max, hi))


def lesson_blooms(lesson: LessonIndex) -> frozenset[str]:
    """مستويات بلوم لأهداف الدرس من الفهرس؛ غير المصنَّف لا يُحسب، فدرس بلا تصنيف بلا بلوم ولا تخمين."""
    return frozenset(b for b in lesson.objectives_bloom if b != "unclassified")


def _stages(
    library: Sequence[Strategy],
    profile: LessonProfile,
    max_dok: int,
    minutes: int = PERIOD_MINUTES,
    chosen_by_teacher: Mapping[str, str] | None = None,
) -> tuple[Stage, ...]:
    """المراحل الست: لكل مرحلة أنسب استراتيجية بلا موارد لبلوم أهداف الدرس وعمق الحصة (`strategies.score`، أو ما اختاره
    المعلم منها)، ثم الدقائق ضمن حدّي المرحلة واستراتيجيتها ومجموعها الزمن."""
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
                strategy = sorted(fits, key=lambda s: (-score(s, profile, ideal[name]), s.slug))[0]
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
    rules = practice_rules(lesson, examples, practice)
    basic_path, advanced_path = rules.paths

    classwork = _classwork(own, edit.removed) if own else ()
    taken = {x for c in classwork for x in c.exercises}
    pool = [
        (d, x)
        for d, x in _exercises_by_depth(practice, practice_only=rules.practice_only)
        if x not in taken and x not in edit.removed
    ]
    basic, advanced, homework = _differentiation(pool, rules)

    measurable = tuple(e.n for e in practice if e.has_generator and not e.conceptual)
    exit_ticket = None
    if not last:
        for c in reversed(classwork):
            if by_n[c.example].has_generator:
                exit_ticket = ExitTicket(c.example, c.dok)
                break

    written = authored or {}
    objectives = tuple(_objective(e, written.get(e.n), audience) for e in own)
    depths = frozenset(d for e in practice for d, _ in e.all_rows)
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
        stages=_stages(
            library,
            LessonProfile(bloom=lesson_blooms(lesson), dok=depths),
            max(depths, default=1),
            chosen_by_teacher=edit.strategies,
        ),
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
