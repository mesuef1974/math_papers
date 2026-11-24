"""معايير عرض الحصة على نموذج الشرائح قبل التصدير (`docs/lesson_prep_plan.md`، «معايير العرض»): حتمية، بلا Django.

هنا S1 إلى S6 وS9 إلى S11 وS13. S7 (وضوح المقطع) وS8 (الهوية) وS12 (فتح الملف وحتميته) على ملف PPTX الناتج في
`apps/planning/pptx_checks.py`، وS14 يدوي. الحاجب الفاشل يمنع التصدير (`blocking_failures`)، والتنبيه (S5 وS11) يظهر للمعلم ولا يمنع.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence

from apps.knowledge.domain.course_index import REPRESENTATIONS
from apps.papers.domain.bidi import isolate_number_ranges, strip_isolation

from .deck import (
    CLIP_KINDS,
    LINE_CHARS,
    MAX_BULLETS,
    MAX_LINES,
    MIN_BODY_PT,
    MIN_TITLE_PT,
    MINUTES_PER_SLIDE,
    PERIOD_TEXT,
    REPRESENTATION_LABELS,
    SLIDE_PHASE,
    ExampleClip,
    PeriodDeck,
    example_alt,
    objective_bullet,
    period_deck_key,
    try_alt,
)
from .prep import STAGE_NAMES, PeriodPrep, Recall
from .prep_checks import PASS, CheckResult, _result, blocking_failures
from .prep_sheet import STAGE_LABELS, recall_label

KEY_PATTERN = re.compile(r"^decks/[\w-]+/[\w.]+-k\d+of\d+-p\d+-[0-9a-f]{16}\.pptx$")
# رمز لكل نوع شريحة، والترتيب (S3): العنوان، الاستدعاء، الأهداف، ثم لكل مثال مقاطعه وحله و«حاول أن تحل» والتدريب الصفي،
# ثم الممارسة المستقلة والفحص وبطاقة الخروج واختبار الدرس والواجب
KIND_CODE = {
    "title": "T",
    "recall": "R",
    "objectives": "O",
    "example": "E",
    "reveal": "V",
    "try": "Y",
    "classwork": "C",
    "differentiation": "D",
    "check": "K",
    "exit": "X",
    "quiz": "Q",
    "homework": "H",
}
ORDER = re.compile(r"^TR?O?(E+VY*C?)*D?K?X?Q?H?$")
TEACHER_MARKERS = ("DOK", "الطور", "الدقائق")
WORD = re.compile(r"[^\W\d_]+")


def _phase_note(slide) -> tuple[str, str]:
    return (
        isolate_number_ranges(
            PERIOD_TEXT["phase_note"].format(phase=STAGE_LABELS.get(slide.phase, slide.phase))
        ),
        isolate_number_ranges(PERIOD_TEXT["minutes_note"].format(minutes=slide.minutes)),
    )


def s1_input(
    deck: PeriodDeck, prep: PeriodPrep, clips: Sequence[ExampleClip], prep_results: Iterable[CheckResult]
):
    """عرض لكل حصة: مدخله تحضير بلا معيار حاجب فاشل ووحدته معتمدة، ومفتاحه من الحصة وزمنها وتجزئة تحضيرها ومقاطعها."""
    results = tuple(prep_results)
    problems = [f"معيار التحضير {r.code} فاشل" for r in blocking_failures(results)]
    approval = next((r for r in results if r.code == "T2c"), None)
    if approval is None or approval.status != PASS:
        problems.append("وحدة الحصة غير معتمدة (T2c)")
    if (deck.course, deck.lesson, deck.k, deck.n, deck.minutes) != (
        prep.course,
        prep.lesson,
        prep.k,
        prep.n,
        prep.minutes,
    ):
        problems.append("هوية العرض لا تطابق الحصة")
    if not KEY_PATTERN.match(deck.key):
        problems.append(f"مفتاح بغير الصيغة: {deck.key}")
    elif deck.key != period_deck_key(prep, clips):
        problems.append("المفتاح لا يطابق تجزئة التحضير والمقاطع")
    return _result("S1", problems)


def s2_examples(deck: PeriodDeck, prep: PeriodPrep) -> CheckResult:
    """شريحة مثال لكل مثال في التحضير وتتماته بعده بأجزاء متصلة، ولا مقطع لمثال خارج الحصة."""
    problems = []
    own = [e.n for e in prep.examples]
    shown: dict[int, list[int]] = {}
    for s in deck.slides:
        if s.kind == "example" and s.clip is not None:
            shown.setdefault(s.clip.n, []).append(s.clip.part)
    for s in deck.slides:
        if s.clip is not None and s.clip.n not in own:
            problems.append(f"مقطع المثال {s.clip.n} خارج الحصة")
    for e in prep.examples:
        parts = shown.get(e.n, [])
        if not parts:
            problems.append(f"المثال {e.n} بلا شريحة")
        elif parts != list(range(1, len(parts) + 1)):
            problems.append(f"المثال {e.n}: أجزاؤه {parts} غير متصلة")
        elif e.continuations is not None and len(parts) != e.continuations:
            problems.append(f"المثال {e.n}: {len(parts)} شرائح ومقاطعه {e.continuations}")
    order = list(dict.fromkeys(s.refs[0] for s in deck.slides if s.kind == "example" and s.refs))
    if order != [n for n in own if n in shown]:
        problems.append(f"ترتيب الأمثلة {order} لا يطابق التحضير {own}")
    return _result("S2", problems)


def s3b_phases(deck: PeriodDeck, prep: PeriodPrep) -> CheckResult:
    """كل شريحة في مرحلة واحدة من مراحل التحضير هي مرحلة نوعها، ولا مرحلة ذات محتوى بلا شريحة."""
    problems = []
    stages = {s.name for s in prep.stages}
    for i, s in enumerate(deck.slides, 1):
        if s.phase not in STAGE_NAMES or s.phase not in stages:
            problems.append(f"الشريحة {i}: مرحلة {s.phase} ليست في التحضير")
        elif SLIDE_PHASE.get(s.kind) != s.phase:
            problems.append(f"الشريحة {i}: النوع {s.kind} ليس في مرحلة {s.phase}")
    content = {
        "warmup": True,
        "objectives": bool(prep.objectives),
        "direct": bool(prep.examples),
        "guided": bool(prep.classwork),
        "independent": bool(prep.basic or prep.advanced),
        "closing": bool(prep.formative or prep.exit_ticket or prep.quiz or prep.homework),
    }
    present = {s.phase for s in deck.slides}
    problems += [
        f"مرحلة {name} ذات محتوى بلا شريحة" for name, has in content.items() if has and name not in present
    ]
    return _result("S3b", problems)


def s3_order(deck: PeriodDeck, prep: PeriodPrep) -> CheckResult:
    """الترتيب يتبع المراحل، وكتلة كل مثال (مقاطعه وحله وتدريبه) متصلة وتخصه وحده."""
    problems = []
    unknown = sorted({s.kind for s in deck.slides} - set(KIND_CODE))
    if unknown:
        return _result("S3", [f"نوع شريحة غير معروف: {unknown}"])
    sequence = "".join(KIND_CODE[s.kind] for s in deck.slides)
    if not ORDER.match(sequence):
        problems.append(f"ترتيب الشرائح {sequence} لا يتبع المراحل")
    block: int | None = None
    for s in deck.slides:
        if s.kind == "example":
            if s.clip is not None and s.clip.part == 1:
                block = s.refs[0] if s.refs else None
        elif s.kind in ("reveal", "try", "classwork"):
            if s.refs != (block,):
                problems.append(f"شريحة {s.kind} للمثال {s.refs} داخل كتلة المثال {block}")
        else:
            block = None
    classwork = {c.example for c in prep.classwork}
    blocks = [s.refs[0] for s in deck.slides if s.kind == "classwork" and s.refs]
    if blocks != [e.n for e in prep.examples if e.n in classwork]:
        problems.append("شرائح التدريب الصفي لا تطابق تدريبات التحضير")
    return _result("S3", problems)


def s4_objectives(deck: PeriodDeck, prep: PeriodPrep) -> CheckResult:
    """شريحة الأهداف تحمل أهداف الحصة بترتيبها ونصوصها، لا أهداف الدرس."""
    problems = []
    slides = [s for s in deck.slides if s.kind == "objectives"]
    if not prep.objectives:
        if slides:
            problems.append("شريحة أهداف لحصة بلا أهداف")
        return _result("S4", problems)
    if len(slides) != 1:
        return _result("S4", [f"{len(slides)} شرائح أهداف بدل واحدة"])
    slide = slides[0]
    expected = tuple(o.example for o in prep.objectives)
    own = {e.n for e in prep.examples}
    if slide.refs != expected:
        problems.append(f"أهداف الأمثلة {slide.refs} بدل {expected}")
    problems += [f"هدف لمثال خارج الحصة: {n}" for n in slide.refs if n not in own]
    bullets = tuple(objective_bullet(prep, i) for i in range(len(prep.objectives)))
    if slide.bullets != bullets:
        problems.append("نصوص الأهداف لا تطابق أهداف الحصة")
    return _result("S4", problems)


def s5_pace(deck: PeriodDeck, prep: PeriodPrep) -> CheckResult:
    """عدد الشرائح لا يتجاوز دقائق الحصة ÷ 2، ولكل شريحة طورها ودقائقها في ملاحظات المتحدث."""
    problems = []
    limit = prep.minutes // MINUTES_PER_SLIDE
    if len(deck.slides) > limit:
        problems.append(f"{len(deck.slides)} شريحة والحد {limit}")
    for i, s in enumerate(deck.slides, 1):
        if s.minutes < 1:
            problems.append(f"الشريحة {i} بلا دقائق")
        if s.notes[:2] != _phase_note(s):
            problems.append(f"الشريحة {i}: الطور والدقائق ليسا أول الملاحظات")
    total = sum(s.minutes for s in deck.slides)
    if total > prep.minutes:
        problems.append(f"مجموع الدقائق {total} أكثر من {prep.minutes}")
    return _result("S5", problems)


def _lines(text: str) -> int:
    return math.ceil(len(strip_isolation(text)) / LINE_CHARS)


def s6_density(deck: PeriodDeck) -> CheckResult:
    """ست نقاط على الأكثر وكل نقطة سطران على الأكثر، والعنوان سطر واحد، وخط النص 24pt فأكثر والعنوان 32pt فأكثر."""
    problems = []
    for i, s in enumerate(deck.slides, 1):
        if len(s.bullets) > MAX_BULLETS:
            problems.append(f"الشريحة {i}: {len(s.bullets)} نقاط")
        problems += [
            f"الشريحة {i}: نقطة أطول من {MAX_LINES} سطرين" for b in s.bullets if _lines(b) > MAX_LINES
        ]
        if _lines(s.title) > 1:
            problems.append(f"الشريحة {i}: العنوان أطول من سطر")
        if s.body_pt < MIN_BODY_PT:
            problems.append(f"الشريحة {i}: خط النص {s.body_pt}pt")
        if s.title_pt < MIN_TITLE_PT:
            problems.append(f"الشريحة {i}: خط العنوان {s.title_pt}pt")
    return _result("S6", problems)


def s9_direction(deck: PeriodDeck) -> CheckResult:
    """كل شريحة من اليمين إلى اليسار، وكل مدى رقمي في نصوصها معزول بـ `isolate_number_ranges`."""
    problems = []
    for i, s in enumerate(deck.slides, 1):
        if not s.rtl:
            problems.append(f"الشريحة {i} ليست من اليمين")
        problems += [
            f"الشريحة {i}: مدى غير معزول في {strip_isolation(t)!r}"
            for t in s.texts
            if isolate_number_ranges(strip_isolation(t)) != t
        ]
    return _result("S9", problems)


def s10_accessibility(deck: PeriodDeck, prep: PeriodPrep) -> CheckResult:
    """عنوان لكل شريحة، ولكل صورة نص بديل برقم المثال وصفحته، والصورة في شرائح الأمثلة وحدها وتخص مثالها."""
    problems = []
    examples = {e.n: e for e in prep.examples}
    for i, s in enumerate(deck.slides, 1):
        if not s.title.strip():
            problems.append(f"الشريحة {i} بلا عنوان")
        if any(not b.strip() for b in s.bullets):
            problems.append(f"الشريحة {i}: نقطة فارغة")
        if (s.clip is not None) != (s.kind in CLIP_KINDS):
            problems.append(f"الشريحة {i}: صورة في غير موضعها ({s.kind})")
        if s.clip is None:
            continue
        e = examples.get(s.clip.n)
        if s.refs != (s.clip.n,):
            problems.append(f"الشريحة {i}: الصورة للمثال {s.clip.n} والشريحة لـ {s.refs}")
        if e is None or s.alt != (try_alt(e) if s.kind == "try" else example_alt(e)):
            problems.append(f"الشريحة {i}: نص بديل ناقص للمثال {s.clip.n}")
    return _result("S10", problems)


def s11_notes(deck: PeriodDeck) -> CheckResult:
    """جانب المعلم في الملاحظات: الطور والدقائق، وعمق كل تمرين في شرائح التمارين، ولا شيء منه على الشريحة."""
    problems = []
    for i, s in enumerate(deck.slides, 1):
        if s.notes[:2] != _phase_note(s):
            problems.append(f"الشريحة {i}: الطور والدقائق ليسا في الملاحظات")
        if s.kind in ("classwork", "differentiation", "homework") and not any("DOK" in n for n in s.notes):
            problems.append(f"الشريحة {i}: عمق التمارين ليس في الملاحظات")
        problems += [
            f"الشريحة {i}: «{m}» على الشريحة"
            for m in TEACHER_MARKERS
            if any(m in t for t in (s.title, *s.bullets))
        ]
    return _result("S11", problems)


def _words(texts: Iterable[str | None]) -> set[str]:
    return {w for t in texts if t for w in WORD.findall(t)}


def allowed_words(prep: PeriodPrep) -> frozenset[str]:
    """كلمات العرض المقرَّرة: قوالبه وتسميات المراحل والتمثيلات والاستدعاء، ورموز المعايير، ونصوص الأهداف المؤلَّفة."""
    templates = [re.sub(r"\{[^}]*\}", " ", t) for t in PERIOD_TEXT.values()]
    recalls = [
        recall_label(Recall(kind, "0", 1)) for kind in ("previous_lesson", "previous_period", "exit_review")
    ]
    recalls.append(recall_label(Recall("prior_knowledge")))
    authored = [p for o in prep.objectives if o.source == "authored" for p in o.parts]
    return frozenset(
        _words(
            [
                *templates,
                *STAGE_LABELS.values(),
                *REPRESENTATION_LABELS.values(),
                *REPRESENTATIONS,
                *recalls,
                *prep.standards,
                *authored,
            ]
        )
    )


def s13_no_guide_text(deck: PeriodDeck, prep: PeriodPrep) -> CheckResult:
    """لا نص دليل: كل كلمة في العرض من قوالبه أو من نص هدف مؤلَّف، ولا مقطع إلا لأمثلة الحصة في شرائح الأمثلة."""
    problems = []
    allowed = allowed_words(prep)
    own = {e.n for e in prep.examples}
    for i, s in enumerate(deck.slides, 1):
        foreign = sorted(_words(s.texts) - allowed)
        if foreign:
            problems.append(f"الشريحة {i}: كلمات من خارج القوالب {foreign[:5]}")
        if s.clip is not None and (s.kind not in CLIP_KINDS or s.clip.n not in own):
            problems.append(f"الشريحة {i}: مقطع خارج أمثلة الحصة")
    return _result("S13", problems)


def check_deck(
    deck: PeriodDeck,
    prep: PeriodPrep,
    clips: Sequence[ExampleClip],
    prep_results: Iterable[CheckResult],
) -> tuple[CheckResult, ...]:
    """معايير العرض الآلية على النموذج بترتيب رموزها."""
    return (
        s1_input(deck, prep, clips, prep_results),
        s2_examples(deck, prep),
        s3b_phases(deck, prep),
        s3_order(deck, prep),
        s4_objectives(deck, prep),
        s5_pace(deck, prep),
        s6_density(deck),
        s9_direction(deck),
        s10_accessibility(deck, prep),
        s11_notes(deck),
        s13_no_guide_text(deck, prep),
    )
