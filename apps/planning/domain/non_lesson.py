"""تحضير حصص غير الدروس (التهيئة والاختبار القصير والمراجعة والاختبار والمشروع والدعم): حتمي، بلا Django.

قرار المالك 2026-11-20 (`docs/lesson_prep_plan.md`، المرحلة 6 الجزء ب): لكل نوع مراحل خاصة مجموعها 45 دقيقة، ونطاق دروس
مشتق من الخطة الفصلية، ورابط إلى ورقة يولّدها «أوراق»: القصير اختبار قصير من دروس وحدته، والمراجعة أوراق عمل نطاق الاختبار
(وحزمة جدوله إن وُجد)، والاختبار ورقته من جدول مواصفاته، والدعم أوراق عمل علاجية بالمستوى السهل لدروس النطاق السابق.
التهيئة والمشروع تحضير بلا ورقة يكمله المعلم. التحضير وWord الآن، والعرض لاحقًا بقرار مستقل.

النطاق: «دروس النطاق» هي الدروس التي دُرّست بعد آخر اختبار قبل الحصة؛ فإن لم يُدرَّس بعده درس (الدعم والمشروع بعد الاختبار
مباشرة) فهي دروس نطاق ذلك الاختبار. المراجعة والدعم يوزّعان دروسهما على حصصهما متصلة بالترتيب.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .plan_periods import PlanPeriod
from .prep import PERIOD_MINUTES
from .prep_checks import FAIL, NON_LESSON_BLOCKING, PASS, PENDING, CheckResult

KINDS = ("orientation", "quiz", "review", "exam", "project", "support")
KIND_LABELS = {
    "orientation": "تهيئة",
    "quiz": "اختبار قصير",
    "review": "مراجعة",
    "exam": "اختبار",
    "project": "مشروع",
    "support": "دعم",
}
SCOPE_LABELS = {"midterm": "منتصف الفصل", "final": "نهاية الفصل"}
PAPER_KINDS = frozenset({"quiz", "review", "exam", "support"})  # أنواع لها ورقة مولَّدة
QUIZ_LESSONS = 2  # سقف دروس الاختبار القصير في المولّد (`papers.services.QUIZ_MAX_LESSONS`)
SUPPORT_LEVEL = "K"  # الدعم علاجي بالمستوى السهل
CHECK_CODES = tuple(sorted(NON_LESSON_BLOCKING))


@dataclass(frozen=True)
class PaperLink:
    """ورقة يولّدها «أوراق» للحصة: نوعها ومدخلاتها كما يطلبها مولّد الأوراق، بلا بذرة (يولّدها المعلم)."""

    kind: str  # quiz | worksheet | exam | bundle
    label: str
    lessons: tuple[str, ...] = ()
    level: str = ""
    blueprint: str = ""


@dataclass(frozen=True)
class Row:
    """صفّا النشاط في نموذج الوزارة (التعليم والتحقق) كصفّي الهدف في حصة الدرس."""

    text: str
    teach_activity: str
    teach_assessment: str
    teach_minutes: int
    check_activity: str
    check_assessment: str
    check_minutes: int


@dataclass(frozen=True)
class NonLessonPrep:
    course: str
    slug: str  # مفتاح البند في المسارات: orientation، quiz-u1، review-midterm...
    kind: str
    title: str
    unit: int
    k: int
    n: int
    scope: tuple[str, ...]  # دروس الحصة نفسها (المراجعة والدعم: نصيبها من دروس النطاق)
    warmup: str
    warmup_minutes: int
    rows: tuple[Row, ...]
    closing: str
    closing_minutes: int
    homework: str
    papers: tuple[PaperLink, ...]
    missing_paper: str = ""  # سبب غياب الورقة حين يحتاجها النوع (لا جدول مواصفات)

    @property
    def minutes(self) -> int:
        return (
            self.warmup_minutes
            + sum(r.teach_minutes + r.check_minutes for r in self.rows)
            + self.closing_minutes
        )


def period_slug(period: PlanPeriod) -> str:
    """مفتاح البند في المسارات بلا نقطتين: «quiz:u1» ← «quiz-u1»."""
    return period.key.replace(":", "-")


def period_title(period: PlanPeriod) -> str:
    entry = period.entry
    label = KIND_LABELS[entry.kind]
    if entry.kind == "quiz":
        return f"{label}: الوحدة {entry.unit}"
    if entry.scope:
        return f"{label} {SCOPE_LABELS.get(entry.scope, entry.scope)}"
    return label


def chunk(items: Sequence[str], n: int, k: int) -> tuple[str, ...]:
    """نصيب الحصة `k` من `n` من قائمة متصلة بالترتيب، والزيادة للحصص الأولى."""
    if not items or n <= 0:
        return ()
    base, extra = divmod(len(items), n)
    start = sum(base + (1 if i < extra else 0) for i in range(k - 1))
    return tuple(items[start : start + base + (1 if k - 1 < extra else 0)])


def scope_lessons(periods: Sequence[PlanPeriod], period: PlanPeriod) -> tuple[str, ...]:
    """دروس نطاق الحصة: ما دُرّس بعد آخر اختبار قبلها، أو نطاق ذلك الاختبار إن لم يُدرَّس بعده درس."""
    before = [p for p in periods if p.number < period.number]
    exams = [i for i, p in enumerate(before) if p.kind == "exam"]

    def lessons(rows: Sequence[PlanPeriod]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(p.lesson for p in rows if p.kind == "lesson" and p.lesson))

    if not exams:
        return lessons(before)
    since = lessons(before[exams[-1] + 1 :])
    if since:
        return since
    earlier = [i for i in exams if before[i].key != before[exams[-1]].key]
    return lessons(before[earlier[-1] + 1 if earlier else 0 : exams[-1] + 1])


def _split(total: int, parts: int) -> list[int]:
    base, extra = divmod(total, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]


def _lesson_rows(
    lessons: Sequence[str], teach: str, teach_check: str, check: str, check_check: str
) -> tuple[Row, ...]:
    teach_minutes, check_minutes = _split(15, len(lessons)), _split(20, len(lessons))
    return tuple(
        Row(
            text=f"الدرس {code}",
            teach_activity=teach.format(code=code),
            teach_assessment=teach_check.format(code=code),
            teach_minutes=teach_minutes[i],
            check_activity=check.format(code=code),
            check_assessment=check_check.format(code=code),
            check_minutes=check_minutes[i],
        )
        for i, code in enumerate(lessons)
    )


def _join(codes: Sequence[str]) -> str:
    return "، ".join(codes)


def build_non_lesson(
    course: str,
    period: PlanPeriod,
    periods: Sequence[PlanPeriod],
    *,
    unit_of: Mapping[str, int],
    blueprints: Mapping[str, tuple[str, str, tuple[str, ...]]],
) -> NonLessonPrep:
    """تحضير حصة غير درس من الخطة. `unit_of` وحدة كل درس، و`blueprints` جدول جاهز لكل نوع اختبار (midterm/final) → (المعرّف،
    العنوان، دروسه). نطاق المراجعة والاختبار دروس جدوله بترتيب الخطة إن وُجد، وإلا ما دُرّس بعد آخر اختبار."""
    entry = period.entry
    kind = entry.kind
    if kind not in KINDS:
        raise ValueError(f"ليست حصة غير درس: {kind}")
    taught = scope_lessons(periods, period)
    if kind in ("review", "exam") and entry.scope in blueprints:
        covered = set(blueprints[entry.scope][2])
        planned = dict.fromkeys(p.lesson for p in periods if p.kind == "lesson" and p.lesson)
        taught = tuple(c for c in planned if c in covered) or taught
    papers: list[PaperLink] = []
    missing = ""
    homework = ""
    if kind == "orientation":
        upcoming = tuple(
            dict.fromkeys(
                p.lesson for p in periods if p.kind == "lesson" and p.lesson and p.number > period.number
            )
        )
        first_unit = unit_of.get(upcoming[0], 1) if upcoming else 1
        scope = tuple(c for c in upcoming if unit_of.get(c) == first_unit)
        unit = first_unit
        warmup, warmup_minutes = "تعارف وتوقعات الفصل وقواعد الحصة", 5
        rows = (
            Row(
                text="التعرّف على المقرر ووحداته ونظام تقويمه",
                teach_activity="عرض خريطة الفصل: الوحدات ودروسها وأسابيع الاختبارات",
                teach_assessment="أسئلة شفهية عن خريطة الفصل",
                teach_minutes=15,
                check_activity=f"نشاط تشخيصي في المعرفة السابقة للوحدة {first_unit}",
                check_assessment="يكمله المعلم",
                check_minutes=20,
            ),
        )
        closing, closing_minutes = "تلخيص التوقعات وأدوات المقرر", 5
    elif kind == "quiz":
        scope = tuple(c for c in taught if unit_of.get(c) == entry.unit) or taught
        unit = entry.unit or (unit_of.get(scope[-1], 0) if scope else 0)
        recent = scope[-QUIZ_LESSONS:]
        if recent:
            papers.append(PaperLink("quiz", f"اختبار قصير: {_join(recent)}", lessons=recent))
        else:
            missing = "لا دروس قبل الاختبار القصير في الخطة"
        warmup, warmup_minutes = f"مراجعة سريعة لأفكار دروس الوحدة {unit}", 5
        rows = (
            Row(
                text=f"اختبار قصير في الوحدة {unit}" + (f": {_join(scope)}" if scope else ""),
                teach_activity="تعليمات الاختبار وتوزيع الأوراق",
                teach_assessment="التأكد من فهم التعليمات",
                teach_minutes=5,
                check_activity="الاختبار القصير"
                + (f" من الدرسين {_join(recent)}" if len(recent) > 1 else ""),
                check_assessment="تصحيح بمفتاح الحل وتوزيع الدرجات",
                check_minutes=25,
            ),
        )
        closing, closing_minutes = "مناقشة الحل وتحديد الأخطاء الشائعة", 10
    elif kind in ("review", "support"):
        scope = chunk(taught, period.n, period.k)
        unit = unit_of.get(scope[0], 0) if scope else 0
        level = SUPPORT_LEVEL if kind == "support" else ""
        for code in scope:
            label = f"ورقة عمل {'علاجية ' if kind == 'support' else ''}{code}"
            papers.append(PaperLink("worksheet", label, lessons=(code,), level=level))
        if kind == "review" and entry.scope in blueprints:
            slug, title, _ = blueprints[entry.scope]
            papers.append(PaperLink("bundle", f"حزمة أوراق عمل: {title}", blueprint=slug))
        if not scope:
            missing = "لا دروس في نطاق الحصة"
        if kind == "review":
            warmup = "استدعاء أفكار دروس الحصة وأمثلتها الأساسية"
            rows = _lesson_rows(
                scope,
                "مراجعة أمثلة الدرس {code} الأساسية",
                "أسئلة موجهة على أمثلة الدرس {code}",
                "ورقة عمل الدرس {code}",
                "تصحيح ثنائي ومتابعة الأداء",
            )
            closing = "تلخيص أفكار الدروس وأسئلة الطلبة"
            homework = "إكمال أوراق عمل المراجعة" if scope else ""
        else:
            warmup = "تشخيص سريع للأخطاء الشائعة في دروس النطاق"
            rows = _lesson_rows(
                scope,
                "إعادة شرح مهارة الدرس {code} بالتمثيل الأبسط",
                "أسئلة تشخيصية على الدرس {code}",
                "ورقة عمل علاجية (سهل) للدرس {code}",
                "متابعة فردية للطلبة المحتاجين",
            )
            closing = "تلخيص ما عولج وتحديد من يحتاج متابعة"
        warmup_minutes, closing_minutes = 5, 5
    elif kind == "exam":
        scope = taught
        unit = unit_of.get(scope[-1], 0) if scope else 0
        if entry.scope in blueprints:
            slug, title, _ = blueprints[entry.scope]
            papers.append(PaperLink("exam", title, blueprint=slug))
        else:
            missing = f"لا جدول مواصفات جاهز لاختبار {SCOPE_LABELS.get(entry.scope or '', entry.scope or '')}"
        warmup, warmup_minutes = "تعليمات الاختبار وتوزيع الكراسات", 5
        rows = (
            Row(
                text=f"{period_title(period)}" + (f": {_join(scope)}" if scope else ""),
                teach_activity="التأكد من بيانات الطلبة وفهم التعليمات",
                teach_assessment="مراقبة",
                teach_minutes=0,
                check_activity="تطبيق الاختبار",
                check_assessment="تصحيح بدليل تقدير الدرجات",
                check_minutes=35,
            ),
        )
        closing, closing_minutes = "جمع الكراسات والتحقق من عددها", 5
    else:  # project
        scope = taught
        unit = unit_of.get(scope[-1], 0) if scope else 0
        warmup, warmup_minutes = "عرض فكرة المشروع ومعايير تقديره", 5
        rows = (
            Row(
                text="مشروع تطبيقي على دروس النطاق" + (f": {_join(scope)}" if scope else ""),
                teach_activity="تقسيم المجموعات وتوزيع المهام",
                teach_assessment="التأكد من فهم كل مجموعة لمهمتها",
                teach_minutes=10,
                check_activity="عمل المجموعات في المشروع",
                check_assessment="سلّم تقدير يكمله المعلم",
                check_minutes=25,
            ),
        )
        closing, closing_minutes = "عرض تقدم المجموعات والخطوة التالية", 5
    return NonLessonPrep(
        course=course,
        slug=period_slug(period),
        kind=kind,
        title=period_title(period),
        unit=unit,
        k=period.k,
        n=period.n,
        scope=scope,
        warmup=warmup,
        warmup_minutes=warmup_minutes,
        rows=rows,
        closing=closing,
        closing_minutes=closing_minutes,
        homework=homework,
        papers=tuple(papers),
        missing_paper=missing,
    )


def check_non_lesson(prep: NonLessonPrep) -> tuple[CheckResult, ...]:
    """N1 الزمن 45 دقيقة، وN2 نطاق دروس غير فارغ (عدا التهيئة)، وN3 ورقة مولَّدة للأنواع التي تحتاجها (معلَّق بلا جدول)."""
    n1 = (
        CheckResult("N1", PASS)
        if prep.minutes == PERIOD_MINUTES
        else CheckResult("N1", FAIL, (f"مجموع الزمن {prep.minutes} لا {PERIOD_MINUTES}",))
    )
    n2 = (
        CheckResult("N2", PASS)
        if prep.scope or prep.kind == "orientation"
        else CheckResult("N2", FAIL, ("لا دروس في نطاق الحصة",))
    )
    if prep.kind not in PAPER_KINDS or prep.papers:
        n3 = CheckResult("N3", PASS)
    elif prep.kind == "exam":
        n3 = CheckResult("N3", PENDING, (prep.missing_paper,))
    else:
        n3 = CheckResult("N3", FAIL, (prep.missing_paper or "لا ورقة مولَّدة للحصة",))
    return (n1, n2, n3)
