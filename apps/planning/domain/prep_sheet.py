"""ورقة تحضير الحصة: نصوص العرض والتصدير المشتقة من `PeriodPrep`، واحدة للصفحة وملف Word بنموذج الوزارة.

كل نص هنا من رموز التحضير وأرقامه ومن عناوين مكتبة الاستراتيجيات، بلا نص دليل. الهدف الذي لم يُعتمد ملف وحدته يظهر
وصفًا مختصرًا بعلامة «معلَّق» (رقم المثال وصفحته وعمقه وفعله) ليكمله المعلم، حتى تصل نصوصه المعتمدة (قرار المالك
2026-11-19). خانة «اليوم والتاريخ» رقم الأسبوع والحصة، والمعلم يضيف تاريخ شعبته.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from apps.papers.domain.book_source import number_list

from .prep import PeriodPrep, PrepExample
from .prep_checks import BLOCKING, WARNING, CheckResult
from .strategies import Strategy

STAGE_LABELS = {
    "warmup": "التهيئة والمراجعة",
    "objectives": "الأهداف والمفردات",
    "direct": "التعليم المباشر",
    "guided": "الممارسة الموجهة",
    "independent": "الممارسة المستقلة المتمايزة",
    "closing": "التقويم الختامي والغلق",
}
SEMESTERS = {1: "الأول", 2: "الثاني", 3: "الثالث"}
PENDING_MARK = "معلَّق"
SUPPORT_SOURCES = "العرض التقديمي للحصة، وورقة عمل مولَّدة من «أوراق»"
CHECK_TITLES = {
    "T1": "التغطية",
    "T2": "صياغة الأهداف",
    "T2b": "اكتمال سلسلة الهدف",
    "T2c": "اعتماد نصوص الوحدة",
    "T3": "المعايير",
    "T4": "التدريب الصفي",
    "T5": "التدرج في العمق",
    "T6": "الزمن والمراحل",
    "T7": "التقويم التكويني",
    "T8": "التمايز",
    "T9": "الواجب",
    "T10": "الربط بما قبلها",
    "T11": "حمل الحصص",
    "T12": "الحصة الأخيرة",
    "T13": "الحقول المغلقة",
}


@dataclass(frozen=True)
class ObjectiveRow:
    """صفّا الهدف في نموذج الوزارة: صف التعليم (المثال و«جرّب») وصف التحقق (التدريب والتقويم)."""

    example: int | None
    text: str
    pending: bool
    teach_activity: str
    teach_assessment: str
    teach_minutes: int
    check_activity: str
    check_assessment: str
    check_minutes: int


@dataclass(frozen=True)
class StageRow:
    name: str
    label: str
    minutes: int
    strategy: str


@dataclass(frozen=True)
class CheckRow:
    code: str
    title: str
    status: str
    kind: str  # blocking | warning
    details: tuple[str, ...]


@dataclass(frozen=True)
class PrepSheet:
    course: str
    lesson: str
    lesson_title: str
    unit: int
    k: int
    n: int
    week: int
    number: int
    minutes: int
    year: str
    semester: str
    grade: str
    unit_label: str
    day_date: str
    outcomes: str
    main_sources: str
    support_sources: str
    warmup: str
    warmup_minutes: int
    objectives: tuple[ObjectiveRow, ...]
    closing: str
    closing_minutes: int
    homework: str
    basic: str
    advanced: str
    quiz: str
    stages: tuple[StageRow, ...]
    checks: tuple[CheckRow, ...]

    @property
    def pending(self) -> bool:
        return any(row.pending for row in self.objectives)


def split_minutes(total: int, parts: int) -> list[int]:
    """يقسم الدقائق على الأهداف أعدادًا صحيحة مجموعها `total`، والزيادة للأهداف الأولى."""
    if parts <= 0:
        return []
    base, extra = divmod(total, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]


def _example_ref(example: PrepExample) -> str:
    return f"مثال {example.n} (ص {example.page})" if example.page else f"مثال {example.n}"


def _recall(prep: PeriodPrep) -> str:
    recall = prep.recall
    if recall.kind == "previous_lesson":
        return f"استدعاء الدرس {recall.lesson}"
    if recall.kind == "previous_period":
        return f"استدعاء أمثلة الحصة {recall.k}"
    if recall.kind == "exit_review":
        return f"مراجعة بطاقة خروج الحصة {recall.k}"
    return "استدعاء المعرفة السابقة"


def _objective_text(prep: PeriodPrep, objective, example: PrepExample) -> tuple[str, bool]:
    if prep.unit_status == "approved" and all(objective.parts):
        return " ".join(p for p in (objective.behavior, objective.condition, objective.criterion) if p), False
    page = f"ص {example.page}، " if example.page else ""
    return (
        f"مثال {example.n} ({page}عمق {objective.dok}، الفعل: {objective.verb}) — "
        f"نص الهدف {PENDING_MARK} حتى اعتماد الوحدة",
        True,
    )


def _outcomes(codes: Sequence[str], texts: Mapping[str, str]) -> str:
    """نتاجات التعلم: رمز كل معيار ووصفه القصير المعتمد بصياغتنا (`standards.json`)، والرمز وحده قبل اعتماد وحدته."""
    return "؛ ".join(f"{code}: {texts[code].rstrip('.')}" if code in texts else code for code in codes)


def _assessment(prep: PeriodPrep, example: PrepExample) -> str:
    if example.conceptual:
        return "أسئلة شفهية عن الاشتقاق (مثال مفاهيمي بلا سؤال خروج)"
    if not example.has_generator:
        return f"سؤال الخروج {PENDING_MARK}: لا صيغة لمهارة المثال {example.n} بعد"
    if prep.exit_ticket and prep.exit_ticket.example == example.n:
        return f"بطاقة خروج من مهارة المثال {example.n} (عمق {prep.exit_ticket.dok})"
    return f"فحص تكويني: سؤال مولَّد من مهارة المثال {example.n}"


def _objective_rows(prep: PeriodPrep, titles: Mapping[str, str]) -> tuple[ObjectiveRow, ...]:
    stages = {s.name: s for s in prep.stages}
    direct, guided, independent = (
        titles.get(stages[name].strategy or "", "") for name in ("direct", "guided", "independent")
    )
    teach_total = stages["direct"].minutes + stages["guided"].minutes
    check_total = stages["independent"].minutes
    if not prep.examples:  # الحصة الأخيرة: التمايز والتقويم واختبار الدرس على أمثلة الدرس كلها
        return (
            ObjectiveRow(
                example=None,
                text="مراجعة أمثلة الدرس وحل تدريباتها بمستويين، ثم اختبار الدرس",
                pending=False,
                teach_activity=f"مراجعة متمايزة ({direct}): أساسي {number_list(list(prep.basic))}",
                teach_assessment=f"ممارسة موجهة ({guided}) ومتابعة الأداء في المجموعات",
                teach_minutes=teach_total,
                check_activity=f"متقدم {number_list(list(prep.advanced))} ({independent})",
                check_assessment="اختبار الدرس بأعماق " + "، ".join(map(str, prep.quiz))
                if prep.quiz
                else "اختبار الدرس",
                check_minutes=check_total,
            ),
        )
    examples = {e.n: e for e in prep.examples}
    classwork = {c.example: c for c in prep.classwork}
    teach = split_minutes(teach_total, len(prep.objectives))
    check = split_minutes(check_total, len(prep.objectives))
    rows = []
    for i, objective in enumerate(prep.objectives):
        example = examples[objective.example]
        text, pending = _objective_text(prep, objective, example)
        work = classwork.get(example.n)
        rows.append(
            ObjectiveRow(
                example=example.n,
                text=text,
                pending=pending,
                teach_activity=f"{_example_ref(example)}: {direct}",
                teach_assessment=f"«جرّب» على المثال {example.n}: {guided}",
                teach_minutes=teach[i],
                check_activity=(
                    f"تدريب صفي {number_list(list(work.exercises))}: {independent}"
                    if work
                    else "مناقشة الاشتقاق وتطبيقه"
                ),
                check_assessment=_assessment(prep, example),
                check_minutes=check[i],
            )
        )
    return tuple(rows)


def _closing(prep: PeriodPrep, title: str) -> str:
    if prep.is_last and prep.quiz:
        return f"{title}: اختبار الدرس وتلخيص أفكاره"
    if prep.exit_ticket:
        return f"{title}: بطاقة خروج من مهارة المثال {prep.exit_ticket.example}"
    return f"{title}: تلخيص أفكار الحصة"


def _checks(results: Sequence[CheckResult]) -> tuple[CheckRow, ...]:
    return tuple(
        CheckRow(
            code=r.code,
            title=CHECK_TITLES.get(r.code, r.code),
            status=r.status,
            kind="blocking" if r.code in BLOCKING else "warning" if r.code in WARNING else "manual",
            details=r.details,
        )
        for r in results
    )


def prep_sheet(
    prep: PeriodPrep,
    checks: Sequence[CheckResult],
    library: Mapping[str, Strategy],
    *,
    lesson_title: str,
    week: int,
    number: int,
    year: str,
    semester: int,
    grade: str,
    standard_texts: Mapping[str, str] | None = None,
) -> PrepSheet:
    titles = {slug: s.title for slug, s in library.items()}
    stages = {s.name: s for s in prep.stages}
    examples = prep.examples or prep.review
    pages = [_example_ref(e) for e in examples]
    return PrepSheet(
        course=prep.course,
        lesson=prep.lesson,
        lesson_title=lesson_title,
        unit=prep.unit,
        k=prep.k,
        n=prep.n,
        week=week,
        number=number,
        minutes=prep.minutes,
        year=year,
        semester=SEMESTERS.get(semester, str(semester)),
        grade=grade,
        unit_label=f"الوحدة {prep.unit}",
        day_date=f"الأسبوع {week}، الحصة {prep.k} من {prep.n}",
        outcomes=_outcomes(prep.standards, standard_texts or {}),
        main_sources="كتاب الطالب: " + "، ".join(pages) if pages else "كتاب الطالب",
        support_sources=SUPPORT_SOURCES,
        warmup=f"{titles.get(stages['warmup'].strategy or '', '')}: {_recall(prep)}",
        warmup_minutes=stages["warmup"].minutes,
        objectives=_objective_rows(prep, titles),
        closing=_closing(prep, titles.get(stages["closing"].strategy or "", "")),
        closing_minutes=stages["closing"].minutes,
        homework=f"تمارين الكتاب {number_list(list(prep.homework))}" if prep.homework else "",
        basic=number_list(list(prep.basic)),
        advanced=number_list(list(prep.advanced)),
        quiz="، ".join(map(str, prep.quiz)),
        stages=tuple(
            StageRow(s.name, STAGE_LABELS[s.name], s.minutes, titles.get(s.strategy or "", ""))
            for s in prep.stages
        ),
        checks=_checks(checks),
    )
