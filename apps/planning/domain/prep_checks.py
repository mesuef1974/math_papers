"""معايير التحضير T1 إلى T13 (`docs/lesson_prep_plan.md`، «معايير التحضير»): حتمية، بلا Django.

كل معيار يعيد `CheckResult` بحالة من ثلاث: ناجح، أو فاشل، أو معلَّق (بياناته لم تصل بعد: نصوص الأهداف من ملف الوحدة،
واعتماده، والمقاطع و«جرّب»؛ قرار المالك 2026-11-19). الحاجب الفاشل يمنع بناء العرض، والمعلَّق لا يُحسب نجاحًا: يصير حاجبًا
فعليًا حين تصل بياناته (المرحلة 3). معايير الدرس (T1 وT3 وT11) على حصصه معًا، والباقي على الحصة الواحدة.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from apps.knowledge.domain.course_index import REPRESENTATIONS
from apps.knowledge.domain.schemas import PRACTICE_CODE

from .prep import (
    HOMEWORK_RANGE,
    MAX_OBJECTIVES,
    PERIOD_MINUTES,
    RECALL_KINDS,
    REJECTED_VERBS,
    SOURCES,
    STAGE_BOUNDS,
    STAGE_NAMES,
    STAGES,
    VERBS_BY_DOK,
    PeriodPrep,
    PrepExample,
    recall_for,
)
from .strategies import Strategy

PASS, FAIL, PENDING = "pass", "fail", "pending"
BLOCKING = frozenset(
    {"T1", "T2", "T2b", "T2c", "T3", "T4", "T5", "T6", "T7", "T8", "T10", "T11", "T12", "T13"}
)
WARNING = frozenset({"T9"})
STANDARD_CODE = re.compile(r"^\d{1,2}[A-Z]?\.\d{1,2}\.\d{1,2}$")
ALL_VERBS = frozenset(v for verbs in VERBS_BY_DOK.values() for v in verbs)


@dataclass(frozen=True)
class CheckResult:
    code: str
    status: str
    details: tuple[str, ...] = ()

    @property
    def blocking(self) -> bool:
        return self.code in BLOCKING


def _result(code: str, problems: Iterable[str], pending: Iterable[str] = ()) -> CheckResult:
    problems, pending = tuple(problems), tuple(pending)
    if problems:
        return CheckResult(code, FAIL, problems)
    return CheckResult(code, PENDING, pending) if pending else CheckResult(code, PASS)


def _exercises(prep: PeriodPrep) -> dict[int, int]:
    """تمرين → عمقه، من صفوف أمثلة الحصة (أو الدرس في الأخيرة)."""
    return {x: d for e in prep.practice_examples for d, ex in e.rows for x in ex}


# ---- معايير الحصة ----


def t2_objectives(prep: PeriodPrep) -> CheckResult:
    """هدف واحد لكل مثال غير إثرائي، بأجزاء ABCD الأربعة، وفعل واحد من جدول عمق مثاله، ولا فعل مرفوض."""
    problems, pending = [], []
    counts = Counter(o.example for o in prep.objectives)
    for e in prep.examples:
        if not e.extension and counts[e.n] != 1:
            problems.append(f"المثال {e.n}: {counts[e.n]} أهداف")
    own = {e.n: e for e in prep.examples}
    for o in prep.objectives:
        if o.example not in own:
            problems.append(f"هدف لمثال ليس في الحصة: {o.example}")
            continue
        if o.verb in REJECTED_VERBS or o.verb not in VERBS_BY_DOK.get(o.dok, ()):
            problems.append(f"المثال {o.example}: الفعل «{o.verb}» ليس من أفعال العمق {o.dok}")
        if o.dok != max(own[o.example].max_dok, 1):
            problems.append(f"المثال {o.example}: عمق الهدف {o.dok} لا يطابق عمق المثال")
        parts = o.parts
        if all(p is None for p in parts):
            pending.append(f"المثال {o.example}: نص الهدف ينتظر ملف الوحدة")
        elif any(not (p or "").strip() for p in parts):
            problems.append(f"المثال {o.example}: جزء من ABCD فارغ")
        elif any(word in (o.behavior or "").split() for word in REJECTED_VERBS):
            problems.append(f"المثال {o.example}: السلوك بفعل مرفوض")
    return _result("T2", problems, pending)


def t2b_chain(prep: PeriodPrep) -> CheckResult:
    """لكل هدف: مثال ومقطعه و«جرّب» وتدريب من صفوف تحليله وسؤال خروج من صيغة المثال نفسه. المفاهيمي بلا تدريب ولا خروج."""
    problems, pending = [], []
    own = {e.n: e for e in prep.examples}
    trained = {c.example for c in prep.classwork if c.exercises}
    for o in prep.objectives:
        e = own.get(o.example)
        if e is None:
            problems.append(f"هدف بلا مثال: {o.example}")
            continue
        if e.continuations is None:
            pending.append(f"المثال {e.n}: المقطع ينتظر الأصول")
        elif e.continuations < 1:
            problems.append(f"المثال {e.n}: بلا مقطع")
        pending.append(f"المثال {e.n}: «جرّب» ينتظر مقاطع التدريب")
        if e.conceptual:
            continue
        if e.n not in trained:
            problems.append(f"المثال {e.n}: بلا تدريب من صفوف تحليله")
        if not e.has_generator:
            problems.append(f"المثال {e.n}: بلا صيغة لسؤال الخروج")
    return _result("T2b", problems, pending)


def t2c_approval(prep: PeriodPrep) -> CheckResult:
    """نصوص أهداف الوحدة ومراحلها معتمدة من المالك قبل أن تصل المعلمين."""
    if prep.unit_status is None:
        return CheckResult("T2c", PENDING, (f"الوحدة {prep.unit}: لم يُولَّد ملفها بعد",))
    if prep.unit_status != "approved":
        return CheckResult("T2c", FAIL, (f"الوحدة {prep.unit}: حالتها {prep.unit_status}",))
    return CheckResult("T2c", PASS)


def t4_classwork(prep: PeriodPrep) -> CheckResult:
    """لكل مثال (غير مفاهيمي) تدريب صفي من صفوف تحليله، ولا تدريب في الحصة من مثال ليس فيها."""
    problems = []
    own = {e.n: e for e in prep.examples}
    for e in prep.examples:
        if e.conceptual:
            continue
        work = [c for c in prep.classwork if c.example == e.n and c.exercises]
        if not work:
            problems.append(f"المثال {e.n}: بلا تدريب صفي")
        for c in work:
            stray = [x for x in c.exercises if e.dok_of(x) is None]
            if stray:
                problems.append(f"المثال {e.n}: تدريب ليس من صفوفه {stray}")
    for c in prep.classwork:
        if c.example not in own:
            problems.append(f"تدريب صفي لمثال ليس في الحصة: {c.example}")
    allowed = _exercises(prep)
    for name, numbers in (("basic", prep.basic), ("advanced", prep.advanced), ("homework", prep.homework)):
        stray = [x for x in numbers if x not in allowed]
        if stray:
            problems.append(f"{name}: تمارين من أمثلة ليست في الحصة {stray}")
    return _result("T4", problems)


def t5_progression(prep: PeriodPrep) -> CheckResult:
    """أعماق التدريب الصفي غير متناقصة، وأعلى عمق في تدريبات الحصة لا يتجاوز أعلى عمق لأمثلتها."""
    problems = []
    depths = [c.dok for c in prep.classwork]
    if any(b < a for a, b in zip(depths, depths[1:], strict=False)):
        problems.append(f"أعماق التدريب الصفي متناقصة: {depths}")
    ceiling = max((e.max_dok for e in prep.practice_examples), default=0)
    allowed = _exercises(prep)
    used = [allowed.get(x, 99) for x in (*prep.basic, *prep.advanced, *prep.homework)]
    used += [c.dok for c in prep.classwork]
    if used and max(used) > ceiling:
        problems.append(f"عمق تدريب {max(used)} فوق أعلى عمق للأمثلة {ceiling}")
    return _result("T5", problems)


def t6_time(prep: PeriodPrep, library: Mapping[str, Strategy]) -> CheckResult:
    """المراحل الست بترتيبها، ومجموعها زمن الحصة، وكل مرحلة ضمن حدّيها وحدّي استراتيجيتها."""
    problems = []
    if tuple(s.name for s in prep.stages) != STAGE_NAMES:
        problems.append(f"ترتيب المراحل: {[s.name for s in prep.stages]}")
    total = sum(s.minutes for s in prep.stages)
    if total != prep.minutes or prep.minutes != PERIOD_MINUTES:
        problems.append(f"مجموع الدقائق {total} لا يساوي {PERIOD_MINUTES}")
    phases = {s[0]: s[4] for s in STAGES}
    for s in prep.stages:
        lo, hi = STAGE_BOUNDS.get(s.name, (0, -1))
        if not lo <= s.minutes <= hi:
            problems.append(f"{s.name}: {s.minutes} دقيقة خارج [{lo}، {hi}]")
        if s.strategy is None:
            if phases.get(s.name):
                problems.append(f"{s.name}: بلا استراتيجية")
            continue
        strategy = library.get(s.strategy)
        if strategy is None or strategy.phase not in phases.get(s.name, ()):
            problems.append(f"{s.name}: استراتيجية لا تخص المرحلة {s.strategy}")
        elif not strategy.min <= s.minutes <= strategy.max:
            problems.append(f"{s.name}: {s.minutes} دقيقة خارج حدّي {s.strategy}")
    return _result("T6", problems)


def t7_assessment(prep: PeriodPrep) -> CheckResult:
    """فحص تكويني يقيس مهارة مثال من الحصة بصيغته، وبطاقة خروج عمقها ضمن أعماق تدريبات الحصة (والأخيرة باختبار الدرس)."""
    problems = []
    practice = {e.n: e for e in prep.practice_examples}
    if not prep.formative:
        problems.append("لا فحص تكويني: لا مثال في الحصة بصيغة")
    for n in prep.formative:
        e = practice.get(n)
        if e is None or not e.has_generator:
            problems.append(f"فحص تكويني على مثال ليس في الحصة أو بلا صيغة: {n}")
    if not prep.is_last:
        ticket = prep.exit_ticket
        depths = {c.dok for c in prep.classwork} | set(_exercises(prep).values())
        if ticket is None:
            problems.append("لا بطاقة خروج")
        elif ticket.example not in practice or not practice[ticket.example].has_generator:
            problems.append(f"بطاقة خروج على مثال ليس في الحصة أو بلا صيغة: {ticket.example}")
        elif ticket.dok not in depths or ticket.dok > max(depths):
            problems.append(f"عمق بطاقة الخروج {ticket.dok} خارج أعماق الحصة")
    return _result("T7", problems)


def t8_differentiation(prep: PeriodPrep) -> CheckResult:
    """قائمتا الأساسي والمتقدم غير فارغتين، ومن دليل المهام وتمارين أمثلة الحصة."""
    problems = []
    basic_path, advanced_path = prep.task_guide
    allowed = _exercises(prep)
    for name, numbers, path in (
        ("basic", prep.basic, basic_path),
        ("advanced", prep.advanced, advanced_path),
    ):
        if not numbers:
            problems.append(f"{name}: فارغة")
        stray = [x for x in numbers if x not in path or x not in allowed]
        if stray:
            problems.append(f"{name}: خارج دليل المهام أو أمثلة الحصة {stray}")
    return _result("T8", problems)


def t9_homework(prep: PeriodPrep) -> CheckResult:
    """الواجب من تمارين أمثلة الحصة وحدها، وعدده بين 3 و8 (تنبيه)."""
    problems = []
    allowed = _exercises(prep)
    if any(x not in allowed for x in prep.homework):
        problems.append("واجب من خارج أمثلة الحصة")
    lo, hi = HOMEWORK_RANGE
    if not lo <= len(prep.homework) <= hi:
        problems.append(f"عدد الواجب {len(prep.homework)} خارج [{lo}، {hi}]")
    return _result("T9", problems)


def t10_recall(prep: PeriodPrep, previous_lesson: str | None, after_break: bool) -> CheckResult:
    """الأولى تستدعي الدرس السابق، وما بعدها الحصة السابقة، وبعد انقطاع بطاقة خروجها."""
    expected = recall_for(prep.k, previous_lesson, after_break)
    if prep.recall != expected:
        return CheckResult("T10", FAIL, (f"الاستدعاء {prep.recall} والمتوقع {expected}",))
    return CheckResult("T10", PASS)


def t12_last_period(prep: PeriodPrep, quiz_depths: Sequence[int]) -> CheckResult:
    """الحصة الأخيرة للتمايز والتقويم بلا مثال جديد، وتحمل اختبار الدرس بأعماقه؛ وما قبلها بلا اختبار الدرس."""
    problems = []
    if prep.is_last:
        if prep.examples or prep.objectives:
            problems.append(f"مثال جديد في الحصة الأخيرة: {[e.n for e in prep.examples]}")
        if not prep.review:
            problems.append("الحصة الأخيرة بلا أمثلة الدرس للمراجعة")
        if not quiz_depths or tuple(prep.quiz) != tuple(quiz_depths):
            problems.append(f"اختبار الدرس {list(prep.quiz)} لا يطابق أعماقه {list(quiz_depths)}")
    elif prep.quiz:
        problems.append("اختبار الدرس قبل الحصة الأخيرة")
    return _result("T12", problems)


def t13_closed_fields(prep: PeriodPrep, library: Mapping[str, Strategy]) -> CheckResult:
    """لا نص من الدليل: كل حقل نصي رمز أو فئة مغلقة أو معرّف من مكتبتنا، والنص الحر من ملف الوحدة المعتمد وحده."""
    problems = []
    examples: list[PrepExample] = [*prep.examples, *prep.review]
    for e in examples:
        if not set(e.representations) <= set(REPRESENTATIONS):
            problems.append(f"المثال {e.n}: تمثيل خارج الفئات")
    problems += [f"معيار بغير رمز: {s!r}" for s in prep.standards if not STANDARD_CODE.match(s)]
    problems += [f"ممارسة بغير رمز: {p!r}" for p in prep.practices if not PRACTICE_CODE.match(p)]
    problems += [
        f"استراتيجية خارج المكتبة: {s.strategy}"
        for s in prep.stages
        if s.strategy and s.strategy not in library
    ]
    problems += [f"مرحلة غير معروفة: {s.name}" for s in prep.stages if s.name not in STAGE_NAMES]
    for o in prep.objectives:
        if o.verb not in ALL_VERBS:
            problems.append(f"المثال {o.example}: فعل خارج الجدول")
        if any(p is not None for p in o.parts) and o.source != "authored":
            problems.append(f"المثال {o.example}: نص هدف من مصدر {o.source}")
        if o.source not in SOURCES:
            problems.append(f"المثال {o.example}: مصدر غير معروف {o.source}")
    if prep.recall.kind not in RECALL_KINDS:
        problems.append(f"استدعاء غير معروف: {prep.recall.kind}")
    problems += [f"مصدر غير معروف: {k}={v}" for k, v in prep.sources.items() if v not in SOURCES]
    if prep.kind != "lesson":
        problems.append(f"نوع حصة غير معروف: {prep.kind}")
    return _result("T13", problems)


# ---- معايير الدرس ----


def t1_coverage(
    preps: Sequence[PeriodPrep], core: Sequence[int], enrichment: Iterable[int] = ()
) -> CheckResult:
    """كل مثال أساسي في حصة واحدة بالضبط، ولا مثال إثرائي إلا امتدادًا معلَّمًا."""
    problems = []
    placed = Counter(e.n for p in preps for e in p.examples if not e.extension)
    for n in core:
        if placed[n] != 1:
            problems.append(f"المثال {n} في {placed[n]} حصص")
    extra = set(placed) - set(core)
    rich = set(enrichment)
    problems += [f"مثال إثرائي بلا علامة امتداد: {n}" for n in sorted(extra & rich)]
    problems += [f"مثال ليس في الدرس: {n}" for n in sorted(extra - rich)]
    return _result("T1", problems)


def t3_standards(preps: Sequence[PeriodPrep], standards: Sequence[str]) -> CheckResult:
    """اتحاد معايير الحصص يساوي معايير الدرس."""
    union = {s for p in preps for s in p.standards}
    if union != set(standards):
        return CheckResult("T3", FAIL, (f"معايير الحصص {sorted(union)} ومعايير الدرس {sorted(standards)}",))
    return CheckResult("T3", PASS)


def t11_load(preps: Sequence[PeriodPrep]) -> CheckResult:
    """ثلاثة أهداف للحصة على الأكثر، والفرق بين أثقل حصة أمثلة وأخفها لا يتجاوز وزن أثقل مثال في الدرس."""
    problems = [
        f"الحصة {p.k}: {len(p.objectives)} أهداف" for p in preps if len(p.objectives) > MAX_OBJECTIVES
    ]
    loads = [sum(e.weight for e in p.examples) for p in preps if p.examples]
    heaviest = max((e.weight for p in preps for e in p.examples), default=0)
    if loads and max(loads) - min(loads) > heaviest:
        problems.append(f"فرق الحمل {max(loads) - min(loads)} يتجاوز {heaviest}: {loads}")
    return _result("T11", problems)


def check_prep(
    prep: PeriodPrep,
    library: Mapping[str, Strategy],
    *,
    previous_lesson: str | None,
    after_break: bool,
    quiz_depths: Sequence[int],
) -> tuple[CheckResult, ...]:
    """معايير الحصة الواحدة بترتيب رموزها."""
    return (
        t2_objectives(prep),
        t2b_chain(prep),
        t2c_approval(prep),
        t4_classwork(prep),
        t5_progression(prep),
        t6_time(prep, library),
        t7_assessment(prep),
        t8_differentiation(prep),
        t9_homework(prep),
        t10_recall(prep, previous_lesson, after_break),
        t12_last_period(prep, quiz_depths),
        t13_closed_fields(prep, library),
    )


def check_lesson(
    preps: Sequence[PeriodPrep], core: Sequence[int], standards: Sequence[str], enrichment: Iterable[int] = ()
) -> tuple[CheckResult, ...]:
    """معايير الدرس على حصصه معًا."""
    return (t1_coverage(preps, core, enrichment), t3_standards(preps, standards), t11_load(preps))


def blocking_failures(results: Iterable[CheckResult]) -> tuple[CheckResult, ...]:
    return tuple(r for r in results if r.blocking and r.status == FAIL)
