"""ورقة تحضير الحصة: نصوص العرض والتصدير المشتقة من `PeriodPrep`، واحدة للصفحة وملف Word بنموذج الوزارة.

كل نص هنا من رموز التحضير وأرقامه ومن عناوين مكتبة الاستراتيجيات، بلا نص دليل. الهدف الذي لم يُعتمد ملف وحدته يظهر
وصفًا مختصرًا بعلامة «معلَّق» (رقم المثال وصفحته وعمقه وفعله) ليكمله المعلم، حتى تصل نصوصه المعتمدة (قرار المالك
2026-11-19). خانة «اليوم والتاريخ» رقم الأسبوع والحصة، والمعلم يضيف تاريخ شعبته.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from apps.papers.domain.book_source import book_ref, numbers_with_pages
from apps.papers.domain.item_bank import Item

from .check_items import (
    OpenQuestion,
    PeriodItems,
    book_exercise,
    item_stem,
    option_label,
    option_text,
    period_items,
    split_check_questions,
)
from .non_lesson import NonLessonPrep, PaperLink
from .prep import PeriodPrep, PrepExample, Recall
from .prep_checks import BLOCKING, NON_LESSON_BLOCKING, WARNING, CheckResult
from .strategies import Strategy, with_roles

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
    "T7": "التقييم البنائي",
    "T8": "التمايز",
    "T9": "الواجب",
    "T10": "الربط بما قبلها",
    "T11": "حمل الحصص",
    "T12": "الحصة الأخيرة",
    "T13": "الحقول المغلقة",
    "N1": "الزمن",
    "N2": "نطاق الدروس",
    "N3": "الورقة المولَّدة",
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
    kind: str = "lesson"  # أو نوع حصة غير الدرس (`non_lesson.KINDS`)
    papers: tuple[PaperLink, ...] = ()  # أوراق «أوراق» المرتبطة بحصة غير الدرس
    scope: tuple[str, ...] = ()  # دروس نطاق حصة غير الدرس

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
    return book_ref("مثال", example.n, example.page)


def _the_ref(example: PrepExample) -> str:
    return book_ref("المثال", example.n, example.page)


def recall_label(recall: Recall) -> str:
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
    return (
        f"{book_ref('مثال', example.n, example.page)} — عمق {objective.dok}، الفعل: {objective.verb} — "
        f"نص الهدف {PENDING_MARK} حتى اعتماد الوحدة",
        True,
    )


def _outcomes(codes: Sequence[str], texts: Mapping[str, str]) -> str:
    """نتاجات التعلم: رمز كل معيار ووصفه القصير المعتمد بصياغتنا (`standards.json`)، والرمز وحده قبل اعتماد وحدته."""
    return "؛ ".join(f"{code}: {texts[code].rstrip('.')}" if code in texts else code for code in codes)


def _item_question(item: Item) -> str:
    options = "، ".join(option_label(i, o.text) for i, o in enumerate(item.options))
    return f"{item_stem(item)} [{options}] (الإجابة: {option_text(item.options[item.answer_index].text)})"


def _open_question(question: OpenQuestion) -> str:
    return f"{item_stem(question.problem)} (الإجابة: {option_text(question.problem.answer)})"


def _book_question(prep: PeriodPrep, n: int) -> str:
    number = book_exercise(prep, n)
    if number is None:
        return ""
    return f"{book_ref('التمرين', number, prep.exercise_pages.get(number))} من كتاب الطالب"


def _formative_question(prep: PeriodPrep, items: PeriodItems, n: int) -> str:
    """سؤال المثال كما على شريحته: بنده الموضوعي إن كانت له شريحة، وإلا سؤاله المقالي؛ الفارغ لمقرر بلا صيغة."""
    with_item, _ = split_check_questions(prep, items)
    if n in with_item:
        return _item_question(items.formative[n])
    return _open_question(items.open[n]) if n in items.open else _book_question(prep, n)


def _assessment(prep: PeriodPrep, example: PrepExample) -> str:
    if example.conceptual:
        return "أسئلة شفهية عن الاشتقاق (مثال مفاهيمي بلا سؤال خروج)"
    if not example.has_generator:
        return f"سؤال الخروج {PENDING_MARK}: لا صيغة لمهارة {_the_ref(example)} بعد"
    items = period_items(prep)
    question = _formative_question(prep, items, example.n) if example.n in prep.formative else ""
    asked = f"تقييم بنائي على {_the_ref(example)}: {question}" if question else ""
    if prep.exit_ticket and prep.exit_ticket.example == example.n:
        ticket = f"بطاقة خروج من مهارة {_the_ref(example)}، عمق {prep.exit_ticket.dok}"
        return f"{asked}؛ {ticket}" if asked else ticket
    return asked or f"تقييم بنائي: سؤال مولَّد من مهارة {_the_ref(example)}"


def _activity(head: str, strategy: Strategy | None) -> str:
    """نشاط تعليم وتعلم بدور المعلم ودور الطالب من استراتيجية مرحلته؛ المرحلة بلا استراتيجية نشاطها وصفه وحده."""
    return with_roles(head, strategy.teacher_role, strategy.student_role) if strategy else head


def _objective_rows(prep: PeriodPrep, library: Mapping[str, Strategy]) -> tuple[ObjectiveRow, ...]:
    stages = {s.name: s for s in prep.stages}
    chosen = {name: library.get(stages[name].strategy or "") for name in ("direct", "guided", "independent")}
    direct, guided, independent = (s.title if s else "" for s in chosen.values())
    teach_total = stages["direct"].minutes + stages["guided"].minutes
    check_total = stages["independent"].minutes
    if not prep.examples:  # الحصة الأخيرة: التمايز والتقويم واختبار الدرس على أمثلة الدرس كلها
        return (
            ObjectiveRow(
                example=None,
                text="مراجعة أمثلة الدرس وحل تدريباتها بمستويين، ثم اختبار الدرس",
                pending=False,
                teach_activity=_activity(
                    f"مراجعة متمايزة ({direct}): أساسي {numbers_with_pages(list(prep.basic), prep.exercise_pages)}",
                    chosen["direct"],
                ),
                teach_assessment=_activity(
                    f"ممارسة موجهة ({guided}) ومتابعة الأداء في المجموعات", chosen["guided"]
                ),
                teach_minutes=teach_total,
                check_activity=_activity(
                    f"متقدم {numbers_with_pages(list(prep.advanced), prep.exercise_pages)} ({independent})",
                    chosen["independent"],
                ),
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
                teach_activity=_activity(f"{_example_ref(example)}: {direct}", chosen["direct"]),
                teach_assessment=_activity(f"«جرّب» على {_the_ref(example)}: {guided}", chosen["guided"]),
                teach_minutes=teach[i],
                check_activity=_activity(
                    f"تدريب صفي {numbers_with_pages(list(work.exercises), prep.exercise_pages)}: {independent}"
                    if work
                    else "مناقشة الاشتقاق وتطبيقه",
                    chosen["independent"],
                ),
                check_assessment=_assessment(prep, example),
                check_minutes=check[i],
            )
        )
    return tuple(rows)


def _warmup_questions(prep: PeriodPrep) -> str:
    """سؤالا التهيئة بإجابتيهما (بندا شريحتي التذكّر نفسهما)."""
    return "".join(
        f" — السؤال {i}: {item_stem(item)} (الإجابة: {option_text(item.options[item.answer_index].text)})"
        for i, item in enumerate(period_items(prep).warmup, 1)
    )


def _closing(prep: PeriodPrep, strategy: Strategy | None) -> str:
    title = strategy.title if strategy else ""
    if prep.is_last and prep.quiz:
        head = f"{title}: اختبار الدرس وتلخيص أفكاره"
    elif prep.exit_ticket:
        n = prep.exit_ticket.example
        head = f"{title}: بطاقة خروج من مهارة {book_ref('المثال', n, prep.pages.get(n))}"
        items = period_items(prep)
        if items.exit is not None:  # سؤال شريحة الخروج نفسه بإجابته
            head += f" — {_item_question(items.exit)}"
        elif items.exit_open is not None:
            head += f" — {_open_question(items.exit_open)}"
        elif book := _book_question(prep, n):
            head += f" — {book}"
    else:
        head = f"{title}: تلخيص أفكار الحصة"
    return _activity(head, strategy)


def _checks(results: Sequence[CheckResult]) -> tuple[CheckRow, ...]:
    return tuple(
        CheckRow(
            code=r.code,
            title=CHECK_TITLES.get(r.code, r.code),
            status=r.status,
            kind="blocking"
            if r.code in BLOCKING | NON_LESSON_BLOCKING
            else "warning"
            if r.code in WARNING
            else "manual",
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
        warmup=_activity(
            f"{titles.get(stages['warmup'].strategy or '', '')}: {recall_label(prep.recall)}{_warmup_questions(prep)}",
            library.get(stages["warmup"].strategy or ""),
        ),
        warmup_minutes=stages["warmup"].minutes,
        objectives=_objective_rows(prep, library),
        closing=_closing(prep, library.get(stages["closing"].strategy or "")),
        closing_minutes=stages["closing"].minutes,
        homework=f"تمارين الكتاب {numbers_with_pages(list(prep.homework), prep.exercise_pages)}"
        if prep.homework
        else "",
        basic=numbers_with_pages(list(prep.basic), prep.exercise_pages),
        advanced=numbers_with_pages(list(prep.advanced), prep.exercise_pages),
        quiz="، ".join(map(str, prep.quiz)),
        stages=tuple(
            StageRow(s.name, STAGE_LABELS[s.name], s.minutes, titles.get(s.strategy or "", ""))
            for s in prep.stages
        ),
        checks=_checks(checks),
    )


def non_lesson_sheet(
    prep: NonLessonPrep,
    checks: Sequence[CheckResult],
    *,
    week: int,
    number: int,
    year: str,
    semester: int,
    grade: str,
) -> PrepSheet:
    """ورقة حصة غير درس بالقالب نفسه: صفوف النشاط مكان صفوف الأهداف، والمراحل التهيئة والنشاط والغلق."""
    body = sum(r.teach_minutes + r.check_minutes for r in prep.rows)
    return PrepSheet(
        course=prep.course,
        lesson=prep.slug,
        lesson_title=prep.title,
        unit=prep.unit,
        k=prep.k,
        n=prep.n,
        week=week,
        number=number,
        minutes=prep.minutes,
        year=year,
        semester=SEMESTERS.get(semester, str(semester)),
        grade=grade,
        unit_label=f"الوحدة {prep.unit}" if prep.unit else "",
        day_date=f"الأسبوع {week}، الحصة {prep.k} من {prep.n}",
        outcomes="",
        main_sources="كتاب الطالب: الدروس " + "، ".join(prep.scope) if prep.scope else "كتاب الطالب",
        support_sources="، ".join(p.label for p in prep.papers) or "يكملها المعلم",
        warmup=prep.warmup,
        warmup_minutes=prep.warmup_minutes,
        objectives=tuple(
            ObjectiveRow(
                example=None,
                text=r.text,
                pending=False,
                teach_activity=r.teach_activity,
                teach_assessment=r.teach_assessment,
                teach_minutes=r.teach_minutes,
                check_activity=r.check_activity,
                check_assessment=r.check_assessment,
                check_minutes=r.check_minutes,
            )
            for r in prep.rows
        ),
        closing=prep.closing,
        closing_minutes=prep.closing_minutes,
        homework=prep.homework,
        basic="",
        advanced="",
        quiz="",
        stages=(
            StageRow("warmup", "التهيئة", prep.warmup_minutes, ""),
            StageRow("activity", "النشاط", body, ""),
            StageRow("closing", "الغلق", prep.closing_minutes, ""),
        ),
        checks=_checks(checks),
        kind=prep.kind,
        papers=prep.papers,
        scope=prep.scope,
    )
