"""قراءة: ملف الدرس الشخصي من الفهرس المشتق لمقرره وسير الحصة المبني عليه. حتمي، بلا نص دليل ولا توكنز.

كل قراءة تأخذ المقرر: الرمز «2.6» درس مختلف في كل كتاب. الافتراضي `PLAN_COURSE` هو المقرر الذي تملك المنصة خطته
الفصلية اليوم؛ مسارات العروض تمرّر مقرر الطلب صراحة.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Count, Prefetch, Q, QuerySet

from apps.assets.models import Asset
from apps.assets.selectors import asset_bytes
from apps.assets.storage import Storage
from apps.curriculum.courses import GRADE10_SLUG, grade_label
from apps.curriculum.models import Course, Lesson
from apps.curriculum.selectors import calendar_data, lessons, term_plan_data
from apps.knowledge.domain.course_index import LessonIndex
from apps.knowledge.domain.unit_prep import approved_standards, unit_prep
from apps.knowledge.models import BookExerciseLink
from apps.knowledge.selectors import course_index, example_numbers, lesson_index
from apps.papers.domain.generators import ERROR_KINDS

from .domain.calendar_engine import Closure, Plan, Slot, Term, allocate, parse_terms, sessions
from .domain.check_items import item_stem, option_text, period_items
from .domain.deck import ExampleClip, content_digest, deck_key_of
from .domain.feedback import ClassOutcome, Decision, decide
from .domain.lesson_package import LessonPackage, compose_package
from .domain.non_lesson import KINDS as NON_LESSON_KINDS
from .domain.non_lesson import NonLessonPrep, build_non_lesson, check_non_lesson
from .domain.objective_text import digest as text_digest
from .domain.objective_text import shared_digest
from .domain.plan_periods import PlanPeriod
from .domain.plan_periods import plan_periods as derive_plan_periods
from .domain.prep import (
    PeriodPrep,
    build_prep,
    lesson_blooms,
    lesson_examples,
    lesson_quiz_depths,
    recall_for,
    stage_options,
)
from .domain.prep import allocate as allocate_examples
from .domain.prep_checks import CheckResult, check_lesson, check_prep
from .domain.prep_override import LessonOverride, OverrideError, parse_override
from .domain.prep_sheet import PrepSheet, non_lesson_sheet, prep_sheet
from .domain.semester_plan import (
    TermPlan,
    check_catalog,
    ministry_slots,
    parse_term_plan,
    plan_items,
    term_for_plan,
)
from .domain.strategies import (
    DEFAULT_PERIOD_MINUTES,
    Flow,
    LessonProfile,
    build_flow,
    load_library,
)
from .example_clips import merge_groups, piece_sizes
from .models import (
    ClassOutcomeRecord,
    DeckBuild,
    ItemResult,
    LessonRunRecord,
    ObjectiveOverride,
    ObjectiveSuggestion,
    PeriodPrepOverride,
    PrepReview,
    SectionStudent,
)

PLAN_COURSE = GRADE10_SLUG  # المقرر الافتراضي للتخطيط: أول مقرر له خطة فصلية في الجداول


def profile_from_lesson(lesson: LessonIndex) -> LessonProfile:
    """بلوم من أهداف الدرس (غير المصنَّف لا يُحسب) وDOK من صفوف تحليل تمارينه؛ ما لم يُقرأ يبقى فارغًا فلا يُخمَّن."""
    return LessonProfile(
        bloom=lesson_blooms(lesson),
        dok=frozenset(row.dok for row in lesson.analysis),
    )


def _indexed_lesson(code: str, course: str) -> LessonIndex:
    lesson = lesson_index(course, code)
    if lesson is None:
        raise KeyError(f"درس غير موجود في فهرس المقرر {course}: {code}")
    return lesson


def lesson_profile(code: str, course: str = PLAN_COURSE) -> LessonProfile:
    return profile_from_lesson(_indexed_lesson(code, course))


def lesson_flow(
    code: str,
    period_minutes: int = DEFAULT_PERIOD_MINUTES,
    resources: Collection[str] = (),
    course: str = PLAN_COURSE,
) -> Flow:
    return build_flow(period_minutes, lesson_profile(code, course), resources=resources)


def lesson_codes(course: str = PLAN_COURSE) -> list[str]:
    return [lesson.lesson for lesson in course_index(course).lessons]


def outcome_records(owner: AbstractBaseUser, section: str | None = None) -> QuerySet[ClassOutcomeRecord]:
    rows = ClassOutcomeRecord.objects.filter(owner=owner).select_related("lesson")
    return rows.filter(section=section) if section else rows


def outcome_of(record: ClassOutcomeRecord) -> ClassOutcome:
    return ClassOutcome(
        record.lesson.code, record.attempted, record.correct, record.pace, frozenset(record.obstacles)
    )


def decision_of(record: ClassOutcomeRecord) -> Decision:
    """القرار يُشتق دائمًا من السجل بالعتبات الحالية ولا يُخزَّن، فتعديل العتبات يسري على النتائج المحفوظة."""
    return decide(outcome_of(record))


def run_reports(owner: AbstractBaseUser, section: str | None = None) -> QuerySet[LessonRunRecord]:
    rows = LessonRunRecord.objects.filter(owner=owner).select_related("lesson")
    return rows.filter(section=section) if section else rows


# ───── تشخيص الخطأ: نتيجة الطالب لكل بند (قرار المالك 2026-11-25) ─────


class SectionNotOwnedError(PermissionError):
    """الشعبة ليست من شعب المعلم: لا طالب له فيها. الرد واحد سواء وُجدت عند غيره أم لم توجد."""


class ResultsNotFoundError(LookupError):
    """لا درس بهذا الرمز في المقرر."""


def owned_sections(owner: AbstractBaseUser) -> list[str]:
    """شعب المعلم: ما له فيه طلاب."""
    rows = SectionStudent.objects.filter(owner=owner).order_by("section")
    return list(rows.values_list("section", flat=True).distinct())


def _owned_lesson(
    owner: AbstractBaseUser, course: str, lesson: str, section: str
) -> tuple[str, QuerySet[SectionStudent], Lesson]:
    """شعبة المعلم ودرسها: `SectionNotOwnedError` لشعبة ليست له قبل أي قراءة أخرى، و`ResultsNotFoundError` لدرس مجهول."""
    section = section.strip()
    roster = SectionStudent.objects.filter(owner=owner, section=section)
    if not section or not roster.exists():
        raise SectionNotOwnedError(f"الشعبة {section} ليست من شعبك")
    record = Lesson.objects.filter(course__slug=course, code=lesson).first()
    if record is None:
        raise ResultsNotFoundError(f"الدرس {lesson} غير موجود في المقرر {course}")
    return section, roster, record


def owned_section(owner: AbstractBaseUser, course: str, lesson: str, section: str) -> str:
    """اسم شعبة المعلم بعد التحقق من ملكيتها ووجود الدرس؛ `SectionNotOwnedError` و`ResultsNotFoundError` كاللوحة."""
    return _owned_lesson(owner, course, lesson, section)[0]


def misconception_board(owner: AbstractBaseUser, course: str, lesson: str, section: str) -> dict:
    """لوحة سوء الفهم لشعبة المعلم في درس: لكل نوع خطأ عدد الطلاب المختلفين الذين وقعوا فيه وقائمتهم والأمثلة التي ظهر
    فيها، تنازليًا بالعدد (والتساوي بترتيب `ERROR_KINDS`).

    الطالب الذي كرر النوع نفسه يُعدّ فيه مرة، ومن وقع في نوعين يظهر في كليهما. `correct` من أُدخلت نتائجهم بلا خطأ،
    و`missing` من لا نتيجة لهم في الدرس. ثلاثة استعلامات مجمَّعة مهما بلغ عدد الطلاب. الأخطاء كما في `section_results`."""
    section, roster, record = _owned_lesson(owner, course, lesson, section)
    in_lesson = Q(results__lesson=record)
    totals = roster.aggregate(
        students=Count("pk", distinct=True),
        entered=Count("pk", filter=in_lesson, distinct=True),
        mistaken=Count("pk", filter=in_lesson & Q(results__correct=False), distinct=True),
    )
    wrong = ItemResult.objects.filter(student__in=roster, lesson=record, correct=False)
    counts = dict(
        wrong.order_by().values_list("error_kind").annotate(students=Count("student_id", distinct=True))
    )
    members: dict[str, dict[int, dict]] = {kind: {} for kind in counts}
    rows = (
        wrong.order_by("student__enrollment_no", "example")
        .values_list(
            "error_kind",
            "student_id",
            "student__enrollment_no",
            "student__first_name",
            "student__last_name",
            "example",
        )
        .distinct()
    )
    for kind, student_id, enrollment_no, first_name, last_name, example in rows:
        student = members[kind].setdefault(
            student_id,
            {
                "enrollment_no": enrollment_no,
                "first_name": first_name,
                "last_name": last_name,
                "examples": [],
            },
        )
        student["examples"].append(example)
    order = {kind: index for index, kind in enumerate(ERROR_KINDS)}
    return {
        "course": course,
        "lesson": record.code,
        "section": section,
        "students": totals["students"],
        "entered": totals["entered"],
        "correct": totals["entered"] - totals["mistaken"],
        "missing": totals["students"] - totals["entered"],
        "kinds": [
            {
                "kind": kind,
                "label": ERROR_KINDS.get(kind, kind),
                "count": counts[kind],
                "examples": sorted({e for student in members[kind].values() for e in student["examples"]}),
                "students": list(members[kind].values()),
            }
            for kind in sorted(counts, key=lambda kind: (-counts[kind], order.get(kind, len(order))))
        ],
    }


def section_results(owner: AbstractBaseUser, course: str, lesson: str, section: str) -> dict:
    """نتائج طلاب شعبة المعلم في بنود درس، وأعداد أخطائها بنوع الخطأ (`ERROR_KINDS`) للتشخيص.

    `SectionNotOwnedError` لشعبة ليست له قبل أي قراءة أخرى، و`ResultsNotFoundError` لدرس مجهول. الطالب بلا نتيجة في
    الدرس يظهر بقائمة فارغة."""
    section, roster, record = _owned_lesson(owner, course, lesson, section)
    students = roster.prefetch_related(
        Prefetch("results", queryset=ItemResult.objects.filter(lesson=record), to_attr="lesson_results")
    )
    rows, kinds, attempted, correct = [], Counter(), 0, 0
    for student in students:
        results = []
        for r in student.lesson_results:
            attempted += 1
            correct += r.correct
            kinds[r.error_kind] += not r.correct
            results.append(
                {
                    "example": r.example,
                    "seed": r.seed,
                    "choice": r.choice,
                    "correct": r.correct,
                    "error_kind": r.error_kind or None,
                    "misconception": ERROR_KINDS.get(r.error_kind),
                }
            )
        rows.append(
            {
                "enrollment_no": student.enrollment_no,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "results": results,
            }
        )
    return {
        "course": course,
        "lesson": record.code,
        "section": section,
        "attempted": attempted,
        "correct": correct,
        "kinds": [
            {"kind": kind, "label": label, "count": kinds[kind]}
            for kind, label in ERROR_KINDS.items()
            if kinds[kind]
        ],
        "students": rows,
    }


class StudentNotFoundError(LookupError):
    """لا طالب بهذا رقم القيد في شعبة المعلم."""


def student_errors(
    owner: AbstractBaseUser, course: str, section: str, enrollment_no: str, lesson: str | None = None
) -> list[dict]:
    """أخطاء طالب في بنود مقرر (أو درس منه) للورقة العلاجية: الدرس والمثال ونوع الخطأ وبذرة البند، بلا اسم ولا رقم قيد.

    `SectionNotOwnedError` لشعبة ليست للمعلم قبل أي قراءة أخرى، و`StudentNotFoundError` لرقم قيد ليس فيها. الطالب بلا
    أخطاء قائمة فارغة."""
    section = section.strip()
    roster = SectionStudent.objects.filter(owner=owner, section=section)
    if not section or not roster.exists():
        raise SectionNotOwnedError(f"الشعبة {section} ليست من شعبك")
    student = roster.filter(enrollment_no=enrollment_no.strip()).first()
    if student is None:
        raise StudentNotFoundError(f"لا طالب بهذا رقم القيد في الشعبة {section}")
    rows = ItemResult.objects.filter(student=student, correct=False, lesson__course__slug=course)
    if lesson is not None:
        rows = rows.filter(lesson__code=lesson)
    return [
        {"lesson": code, "example": example, "error_kind": kind, "seed": seed}
        for code, example, kind, seed in rows.order_by("lesson__code", "example", "seed").values_list(
            "lesson__code", "example", "error_kind", "seed"
        )
    ]


def class_errors(owner: AbstractBaseUser, course: str, lesson: str, section: str) -> list[dict]:
    """أخطاء كل طالب أخطأ في بنود درس من شعبة المعلم، بترتيب رقم القيد واستعلام واحد للأخطاء: هويته (رقم القيد والاسم)
    وأخطاؤه بشكل `student_errors`. للحزمة العلاجية وحدها؛ `SectionNotOwnedError` و`ResultsNotFoundError` كاللوحة."""
    _, roster, record = _owned_lesson(owner, course, lesson, section)
    rows = (
        ItemResult.objects.filter(student__in=roster, lesson=record, correct=False)
        .order_by("student__enrollment_no", "example", "seed")
        .values_list(
            "student__enrollment_no",
            "student__first_name",
            "student__last_name",
            "example",
            "error_kind",
            "seed",
        )
    )
    students: dict[str, dict] = {}
    for number, first, last, example, kind, seed in rows:
        student = students.setdefault(
            number, {"enrollment_no": number, "first_name": first, "last_name": last, "errors": []}
        )
        student["errors"].append(
            {"lesson": record.code, "example": example, "error_kind": kind, "seed": seed}
        )
    return list(students.values())


def _course_plan(course: str) -> tuple[Course, TermPlan]:
    row, raw = term_plan_data(course)
    plan = parse_term_plan(raw, row.semester)
    check_catalog(plan, list(lessons(row).values_list("code", flat=True)), example_numbers(course))
    return row, plan


def term_plan(course: str = PLAN_COURSE) -> TermPlan:
    """خطة الوزارة الفصلية للمقرر من جداولها، بعد مطابقة دروسها على جدول دروسه وأمثلتها الإثرائية على أمثلته المحمَّلة (فهرس مشتق أو معرفة بصياغتنا). `KeyError` بلا خطة."""
    return _course_plan(course)[1]


def plan_periods(course: str = PLAN_COURSE) -> tuple[PlanPeriod, ...]:
    """حصص الخطة الفصلية للمقرر مرقّمة: `k` من `n` لكل بند عبر الأسابيع، ورقمها في الفصل وأسبوعها. `KeyError` بلا خطة."""
    return derive_plan_periods(course, term_plan(course))


def calendar_terms(year: str) -> dict[str, Term]:
    """فصول تقويم السنة الأكاديمية من جداوله بمعرّفاتها «t1» و«t2»."""
    return parse_terms(calendar_data(year))


def term1_schedule(
    slots: Collection[Slot] | None = None, course: str = PLAN_COURSE
) -> tuple[TermPlan, list, Plan]:
    """توزيع بنود الوزارة على حصص شعبة (الافتراضي خمس حصص أسبوعيًا): الخطة والبنود وما وضعه المحرك."""
    row, plan = _course_plan(course)
    term = term_for_plan(calendar_terms(row.academic_year)[plan.term_id], plan)
    lost = [Closure(d, d, "other", "يوم فاقد") for d in plan.lost_days]
    free = sessions(term, slots or ministry_slots(), lost)
    items = plan_items(plan)
    return plan, items, allocate(items, free)


# ───── عروض الحصص من تحضيرها ومقاطع الأصول المنشورة (المرحلة 4) ─────
PPTX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def deck_assets(course_slug: str, lesson_code: str, numbers: Collection[int]) -> list[Asset]:
    """مقاطع أمثلة الحصة المنشورة (أرقامها `numbers`) ومقاطع «حاول أن تحل» لها إن نُشرت، بترتيب النوع فالمثال فتتمته."""
    return list(
        Asset.objects.filter(
            course__slug=course_slug,
            lesson__code=lesson_code,
            kind__in=(Asset.Kind.EXAMPLE, Asset.Kind.PRACTICE),
            number__in=numbers,
        ).order_by("kind", "number", "part")
    )


def deck_key(prep: PeriodPrep, assets: Sequence[Asset]) -> str:
    """مفتاح عرض الحصة من فهرس الأصول وحده (تجزئة كل مقطع مخزَّنة معه) فلا تُقرأ الصور لمعرفة الحالة."""

    def digests(kind: str):
        return ((a.number, a.part + 1, content_digest(a.sha256, a.cuts)) for a in assets if a.kind == kind)

    return deck_key_of(prep, digests(Asset.Kind.EXAMPLE), digests(Asset.Kind.PRACTICE))


def clips_of(assets: Sequence[Asset], storage: Storage | None = None) -> tuple[ExampleClip, ...]:
    """مقاطع المخزن كمدخلات عرض: الأصل part=0 يصير جزءًا 1 وتتمته 2 فما فوق."""
    return tuple(
        ExampleClip(
            n=a.number,
            png=asset_bytes(a, storage),
            width_px=a.width,
            height_px=a.height,
            part=a.part + 1,
            kind=a.kind,
            cuts=tuple(a.cuts or ()),
        )
        for a in assets
    )


@dataclass(frozen=True)
class PreparedPeriod:
    """تحضير حصة من حصص الخطة مع نتائج معاييرها (معايير الحصة ثم معايير درسها)."""

    period: PlanPeriod
    prep: PeriodPrep
    checks: tuple[CheckResult, ...]
    allocation: tuple[tuple[int, ...], ...] = ()  # أمثلة كل حصة من حصص الدرس كما بُني التحضير
    default_allocation: tuple[tuple[int, ...], ...] = ()  # توزيع `allocate` المشتق
    override: str = "none"  # none | active | invalid (تعديل محفوظ لم يعد يطابق الدرس فأُهمل)


def _example_clips(course: str) -> dict[str, dict[int, list[list[tuple[int, int]]]]] | None:
    """لكل مثال مقاطعه (الأصل فتتماته بترتيبها)، ولكل مقطع أبعاد أجزائه بعد قصّه، من فهرس الأصول؛ None إن لم يُنشر للمقرر أصل بعد (فالمقطع معلَّق لا مفقود)."""
    rows = Asset.objects.filter(course__slug=course, kind=Asset.Kind.EXAMPLE).order_by("part")
    if not rows.exists():
        return None
    clips: dict[str, dict[int, list[list[tuple[int, int]]]]] = {}
    fields = ("lesson__code", "number", "width", "height", "cuts")
    for code, number, width, height, cuts in rows.values_list(*fields):
        clips.setdefault(code, {}).setdefault(number, []).append(piece_sizes(width, height, cuts))
    return clips


def lesson_preps(
    course: str = PLAN_COURSE, overrides: Mapping[str, object] | None = None, *, strict: bool = False
) -> tuple[PreparedPeriod, ...]:
    """تحضير كل حصة دروس في الخطة الفصلية بترتيبها، مشتقًّا من الفهرس والخطة والمكتبة، مع معاييره T1 إلى T13.

    `overrides` تعديل معلم واحد لكل درس (رمزه → الشكل المحفوظ، `domain/prep_override.py`) يدخل الاشتقاق نفسه. المحفوظ الذي لم
    يعد يطابق الدرس (تغيّر الفهرس أو المكتبة) يُهمل وتُعلَّم حصصه `invalid`؛ و`strict` يرفعه `OverrideError` (للحفظ)."""
    from apps.papers.domain.generators import SKILL_EXAMPLES

    plan = term_plan(course)
    periods = [p for p in plan_periods(course) if p.kind == "lesson"]
    index = {lesson.lesson: lesson for lesson in course_index(course).lessons}
    library = load_library()
    by_slug = {s.slug: s for s in library}
    clips = _example_clips(course)
    generators: dict[str, set[int]] = {}
    for (c, code, _), number in SKILL_EXAMPLES.items():
        if c == course:
            generators.setdefault(code, set()).add(number)

    order = plan.lessons()
    titles = dict(Lesson.objects.filter(course__slug=course).values_list("code", "title"))
    out: list[PreparedPeriod] = []
    for position, code in enumerate(order):
        lesson = index[code]
        rows = [p for p in periods if p.lesson == code]
        enrichment = plan.enrichment_examples.get(code, ())
        sizes = None if clips is None else clips.get(code, {})
        examples = lesson_examples(
            lesson,
            course,
            enrichment=enrichment,
            generators=generators.get(code, ()),
            clips=None if sizes is None else {n: len(parts) for n, parts in sizes.items()},
            slides=None
            if sizes is None
            else {n: len(merge_groups([s for part in parts for s in part])) for n, parts in sizes.items()},
        )
        default_groups = allocate_examples([(e.n, e.weight) for e in examples], len(rows))
        edit, state = LessonOverride(), "none"
        if overrides and code in overrides:
            try:
                edit = parse_override(
                    overrides[code], examples=[e.n for e in examples], n=len(rows), library=library
                )
                state = "active"
            except OverrideError:
                if strict:
                    raise
                state = "invalid"
        groups = edit.groups(default_groups)
        unit = unit_prep(course, lesson.unit)
        previous_lesson = order[position - 1] if position else None
        built = []
        for i, period in enumerate(rows):
            after_break = i > 0 and (
                rows[i - 1].week != period.week or rows[i - 1].number != period.number - 1
            )
            prep = build_prep(
                course=course,
                lesson=lesson,
                examples=examples,
                groups=groups,
                k=period.k,
                recall=recall_for(period.k, previous_lesson, after_break),
                library=library,
                unit_status=None if unit is None else unit.status,
                authored=None if unit is None else unit.objectives(code),
                audience=None if unit is None else unit.audience,
                teacher=edit.edit_for(period.k, default_groups),
            )
            prep = replace(prep, lesson_title=titles.get(code, ""))
            if period.k == 1 and position:
                prep = replace(prep, earlier_lessons=tuple(order[:position]))
            checks = check_prep(
                prep,
                by_slug,
                previous_lesson=previous_lesson,
                after_break=after_break,
                quiz_depths=lesson_quiz_depths(lesson, examples),
            )
            built.append((period, prep, checks))
        lesson_checks = check_lesson(
            [p for _, p, _ in built], [e.n for e in examples], lesson.standards, enrichment
        )
        out += [
            PreparedPeriod(
                period, prep, checks + lesson_checks, groups, tuple(map(tuple, default_groups)), state
            )
            for period, prep, checks in built
        ]
    return tuple(out)


class PrepNotFoundError(LookupError):
    """لا مقرر ولا حصة دروس بهذا الرمز في خطته الفصلية."""


def _plan_course(course: str) -> Course:
    found = Course.objects.filter(slug=course, term_plan__isnull=False).first()
    if found is None:
        raise PrepNotFoundError(f"لا خطة فصلية للمقرر {course}")
    try:
        course_index(course)  # التحضير يُشتق من فهرس المقرر نفسه، ولا يستعير فهرس مقرر آخر
    except KeyError as error:
        raise PrepNotFoundError(f"لا فهرس للمقرر {course}") from error
    return found


def prep_overrides(course: str, owner: AbstractBaseUser | None) -> dict[str, object]:
    """تعديلات المعلم المحفوظة لدروس المقرر: رمز الدرس → الشكل المحفوظ. بلا معلم: لا تعديل (التحضير المشترك)."""
    if owner is None:
        return {}
    rows = PeriodPrepOverride.objects.filter(owner=owner, lesson__course__slug=course)
    return dict(rows.values_list("lesson__code", "data"))


def owner_preps(course: str, owner: AbstractBaseUser | None) -> tuple[PreparedPeriod, ...]:
    """حصص الدروس بتحضير المعلم: المشترك وعليه تعديله إن وُجد."""
    return lesson_preps(course, prep_overrides(course, owner))


def _period_rows(course: str, owner: AbstractBaseUser | None = None) -> list[tuple[PreparedPeriod, dict]]:
    found = _plan_course(course)
    titles = dict(lessons(found).values_list("code", "title"))
    out = []
    for item in owner_preps(course, owner):
        statuses = {c.status for c in item.checks if c.blocking}
        row = {
            "lesson": item.prep.lesson,
            "title": titles.get(item.prep.lesson, ""),
            "unit": item.prep.unit,
            "k": item.prep.k,
            "n": item.prep.n,
            "week": item.period.week,
            "status": "fail" if "fail" in statuses else "pending" if "pending" in statuses else "pass",
            "customized": item.override == "active",
            "kind": "lesson",
        }
        out.append((item, row))
    return out


def _status(checks: Sequence[CheckResult]) -> str:
    statuses = {c.status for c in checks if c.blocking}
    return "fail" if "fail" in statuses else "pending" if "pending" in statuses else "pass"


@dataclass(frozen=True)
class NonLessonPeriod:
    """حصة غير درس من الخطة بتحضيرها ومعاييرها N1 إلى N3."""

    period: PlanPeriod
    prep: NonLessonPrep
    checks: tuple[CheckResult, ...]


def _exam_blueprints(found: Course) -> dict[str, tuple[str, str, tuple[str, ...]]]:
    """جدول مواصفات جاهز لكل نوع اختبار في سنة المقرر وفصله (للفصل كاملًا): النوع → (المعرّف، العنوان، دروسه)."""
    from apps.papers.services import ready_blueprints

    out: dict[str, tuple[str, str, tuple[str, ...]]] = {}
    for row in ready_blueprints():
        if (
            row.course_id == found.pk
            and row.academic_year == found.academic_year
            and row.semester == found.semester
            and row.scope == "full"
        ):
            codes = tuple(dict.fromkeys(item.lesson.code for item in row.items.all()))
            out.setdefault(row.assessment, (row.slug, row.title, codes))
    return out


def non_lesson_preps(course: str = PLAN_COURSE) -> tuple[NonLessonPeriod, ...]:
    """تحضير كل حصة غير درس في الخطة بترتيبها (`domain/non_lesson.py`): مشترك للمقرر، بلا تعديل معلم."""
    found = _plan_course(course)
    periods = plan_periods(course)
    unit_of = {lesson.lesson: lesson.unit for lesson in course_index(course).lessons}
    blueprints = _exam_blueprints(found)
    out = []
    for period in periods:
        if period.kind not in NON_LESSON_KINDS:
            continue
        prep = build_non_lesson(course, period, periods, unit_of=unit_of, blueprints=blueprints)
        out.append(NonLessonPeriod(period, prep, check_non_lesson(prep)))
    return tuple(out)


def prep_periods(course: str, owner: AbstractBaseUser | None = None) -> list[dict]:
    """حصص الخطة كلها بترتيبها مع حالة معاييرها: حصص الدروس بتحضير المعلم، وحصص غير الدروس بتحضيرها المشترك."""
    rows = [(item.period.number, row) for item, row in _period_rows(course, owner)]
    for item in non_lesson_preps(course):
        rows.append(
            (
                item.period.number,
                {
                    "lesson": item.prep.slug,
                    "title": item.prep.title,
                    "unit": item.prep.unit,
                    "k": item.prep.k,
                    "n": item.prep.n,
                    "week": item.period.week,
                    "status": _status(item.checks),
                    "customized": False,
                    "kind": item.prep.kind,
                },
            )
        )
    return [row for _, row in sorted(rows, key=lambda pair: pair[0])]


def deck_periods(course: str, owner: AbstractBaseUser | None = None) -> list[dict]:
    """حصص الدروس بترتيب الخطة لصفحة العروض بتحضير المعلم: حالة معاييرها وعدد أمثلتها، و`clips` صادقة حين نُشر مقطع لكل
    مثال فيها، و`stale` صادقة حين يخالف آخر عرض طلبه المعلم للحصة مفتاحَ تحضيره الحالي (عدّل تحضيره بعده)."""
    by_lesson: dict[str, list[Asset]] = {}
    rows = Asset.objects.filter(
        course__slug=course, kind__in=(Asset.Kind.EXAMPLE, Asset.Kind.PRACTICE)
    ).order_by("kind", "number", "part")
    for asset in rows.select_related("lesson"):
        by_lesson.setdefault(asset.lesson.code, []).append(asset)
    built: dict[tuple[str, int], str] = {}
    if owner is not None:
        builds = DeckBuild.objects.filter(owner=owner, lesson__course__slug=course)
        built = {(code, k): key for code, k, key in builds.values_list("lesson__code", "k", "key")}
    out = []
    for item, row in _period_rows(course, owner):
        numbers = {e.n for e in item.prep.examples}
        assets = [a for a in by_lesson.get(item.prep.lesson, []) if a.number in numbers]
        last = built.get((item.prep.lesson, item.prep.k))
        out.append(
            {
                **row,
                "examples": len(numbers),
                "clips": numbers <= {a.number for a in assets if a.kind == Asset.Kind.EXAMPLE},
                "stale": last is not None and last != deck_key(item.prep, assets),
            }
        )
    return out


def period_item(course: str, lesson: str, k: int, owner: AbstractBaseUser | None = None) -> PreparedPeriod:
    """حصة واحدة (الدرس ورقمها فيه) بتحضيرها ومعاييره: المشترك، أو تحضير المعلم بتعديله إن أُعطي."""
    _plan_course(course)
    item = next((p for p in owner_preps(course, owner) if p.prep.lesson == lesson and p.prep.k == k), None)
    if item is None:
        raise PrepNotFoundError(f"لا حصة {k} للدرس {lesson} في خطة {course}")
    return item


def entry_items(owner: AbstractBaseUser, course: str, lesson: str) -> dict:
    """بنود بطاقات الخروج لدرس كما عُرضت على طلاب المعلم: لكل حصة بندها بمثاله وبذرته من `period_items` نفسه الذي يبني
    العرض والتحضير (بتعديل المعلم إن وُجد)، بنص السؤال والخيارات بترتيبها وبلا أي دلالة على الصحيح ولا نوع الخطأ.

    الحصة بلا بطاقة خروج أو بلا بند موضوعي يصلح للشريحة لا بند لها. `PrepNotFoundError` لمقرر بلا خطة أو درس ليس فيها."""
    _plan_course(course)
    preps = [p.prep for p in owner_preps(course, owner) if p.prep.lesson == lesson]
    if not preps:
        raise PrepNotFoundError(f"لا حصص للدرس {lesson} في خطة {course}")
    rows = []
    for prep in preps:
        items = period_items(prep)
        if items.exit is None or items.exit_seed is None or prep.exit_ticket is None:
            continue
        rows.append(
            {
                "k": prep.k,
                "n": prep.n,
                "example": prep.exit_ticket.example,
                "seed": items.exit_seed,
                "stem": item_stem(items.exit),
                "options": [option_text(option.text) for option in items.exit.options],
            }
        )
    return {"course": course, "lesson": lesson, "items": rows}


def _render(course: str, item: PreparedPeriod, prep: PeriodPrep) -> PrepSheet:
    found = _plan_course(course)
    title = lessons(found).filter(code=prep.lesson).values_list("title", flat=True).first() or ""
    return prep_sheet(
        prep,
        item.checks,
        {s.slug: s for s in load_library()},
        lesson_title=title,
        week=item.period.week,
        number=item.period.number,
        year=found.academic_year,
        semester=found.semester,
        grade=grade_label(found.grade, found.track),
        standard_texts=approved_standards(course),
    )


def period_sheet(course: str, lesson: str, k: int) -> PrepSheet:
    """ورقة تحضير حصة واحدة بنصوصها المعتمدة ومعاييرها (بلا نسخة معلم)."""
    item = period_item(course, lesson, k)
    return _render(course, item, item.prep)


def non_lesson_sheet_of(course: str, slug: str, k: int) -> PrepSheet | None:
    """ورقة حصة غير درس بمفتاح بندها («quiz-u1») ورقمها فيه؛ None إن لم يكن المفتاح بند غير درس."""
    if slug.split("-", 1)[0] not in NON_LESSON_KINDS:
        return None
    found = _plan_course(course)
    item = next((p for p in non_lesson_preps(course) if p.prep.slug == slug and p.prep.k == k), None)
    if item is None:
        raise PrepNotFoundError(f"لا حصة {k} للبند {slug} في خطة {course}")
    return non_lesson_sheet(
        item.prep,
        item.checks,
        week=item.period.week,
        number=item.period.number,
        year=found.academic_year,
        semester=found.semester,
        grade=grade_label(found.grade, found.track),
    )


# ───── مراجعة المعلم لأهداف حصته (docs/teacher_objective_review_plan.md) ─────


@dataclass(frozen=True)
class ObjectiveState:
    """حال هدف مثال عند معلم: النص المعتمد، ونسخته إن عدّل، وقِدمها، وآخر اقتراح له."""

    example: int
    shared: dict | None  # السلوك والشرط والمعيار المعتمدة؛ None قبل اعتماد الوحدة
    mine: dict | None  # الشرط والمعيار في نسخة المعلم
    stale: bool
    editable: bool
    suggestion: dict | None


@dataclass(frozen=True)
class TeacherSheet:
    sheet: PrepSheet
    objectives: dict[int, ObjectiveState]
    review: dict | None
    edit: dict = field(default_factory=dict)


def prep_edit(item: PreparedPeriod, stored: object) -> dict:
    """ما تحتاجه واجهة تعديل الحصة: توزيع الدرس الحالي والمشتق، وبدائل كل مرحلة واختيار المعلم، وتمارين الحصة وما حذفه."""
    library = load_library()
    period = {}
    if item.override == "active" and isinstance(stored, dict):
        period = stored.get("periods", {}).get(str(item.prep.k), {})
    return {
        "state": item.override,
        "allocation": [list(g) for g in item.allocation],
        "default_allocation": [list(g) for g in item.default_allocation],
        "stages": [
            {
                "name": stage.name,
                "current": stage.strategy,
                "chosen": period.get("strategies", {}).get(stage.name),
                "options": [{"slug": o.slug, "title": o.title} for o in stage_options(library, stage.name)],
            }
            for stage in item.prep.stages
            if stage.strategy is not None
        ],
        "exercises": sorted({x for e in item.prep.practice_examples for _, ex in e.all_rows for x in ex}),
        "removed": sorted(period.get("removed", [])),
    }


def sheet_digest(sheet: PrepSheet) -> str:
    """بصمة نصوص أهداف الحصة كما تظهر للمعلم: علامة المراجعة تحتاج تجديدًا إن تغيّرت."""
    return text_digest(row.text for row in sheet.objectives)


def _suggestion_view(row: ObjectiveSuggestion, shared: tuple[str | None, str | None]) -> dict:
    applied = row.decision == ObjectiveSuggestion.ACCEPTED and (row.condition, row.criterion) == shared
    return {
        "status": "applied" if applied else row.decision,
        "condition": row.condition,
        "criterion": row.criterion,
        "note": row.decision_note,
        "created_at": row.created_at,
    }


def teacher_sheet(course: str, lesson: str, k: int, owner: AbstractBaseUser) -> TeacherSheet:
    """ورقة الحصة بنسخة المعلم: الشرط والمعيار من نسخته حين تختلف عن المعتمد، والمعايير T1 إلى T13 كما هي
    (السلوك وفعله وعمقه لا تتغير). الوحدة غير المعتمدة لا تُعدَّل فتظهر كما هي. حصة غير الدرس مشتركة بلا تعديل."""
    other = non_lesson_sheet_of(course, lesson, k)
    if other is not None:
        return TeacherSheet(other, {}, None)
    stored = prep_overrides(course, owner)
    _plan_course(course)
    item = next((p for p in lesson_preps(course, stored) if p.prep.lesson == lesson and p.prep.k == k), None)
    if item is None:
        raise PrepNotFoundError(f"لا حصة {k} للدرس {lesson} في خطة {course}")
    prep = item.prep
    editable = prep.unit_status == "approved"
    record = Lesson.objects.filter(course__slug=course, code=lesson).first()
    numbers = [o.example for o in prep.objectives]
    overrides: dict[int, ObjectiveOverride] = {}
    suggestions: dict[int, ObjectiveSuggestion] = {}
    if editable and record is not None:
        overrides = {
            o.example: o
            for o in ObjectiveOverride.objects.filter(owner=owner, lesson=record, example__in=numbers)
        }
        for row in ObjectiveSuggestion.objects.filter(
            owner=owner, lesson=record, example__in=numbers
        ).order_by("created_at", "id"):
            suggestions[row.example] = row  # الأحدث يغلب
    states: dict[int, ObjectiveState] = {}
    personal = []
    for objective in prep.objectives:
        shared_pair = (objective.condition, objective.criterion)
        override = overrides.get(objective.example)
        mine = override if override and (override.condition, override.criterion) != shared_pair else None
        if mine is not None:
            objective = replace(
                objective, condition=mine.condition, criterion=mine.criterion, source="teacher"
            )
        personal.append(objective)
        original = next(o for o in prep.objectives if o.example == objective.example)
        states[objective.example] = ObjectiveState(
            example=objective.example,
            shared=(
                {
                    "behavior": original.behavior,
                    "condition": original.condition,
                    "criterion": original.criterion,
                }
                if editable
                else None
            ),
            mine=None if mine is None else {"condition": mine.condition, "criterion": mine.criterion},
            stale=mine is not None and mine.base_digest != shared_digest(original),
            editable=editable,
            suggestion=(
                _suggestion_view(suggestions[objective.example], shared_pair)
                if objective.example in suggestions
                else None
            ),
        )
    sheet = _render(course, item, replace(prep, objectives=tuple(personal)))
    review = None
    if record is not None:
        mark = PrepReview.objects.filter(owner=owner, lesson=record, k=k).first()
        if mark is not None:
            review = {"reviewed_at": mark.reviewed_at, "stale": mark.digest != sheet_digest(sheet)}
    return TeacherSheet(
        sheet=sheet, objectives=states, review=review, edit=prep_edit(item, stored.get(lesson))
    )


@dataclass(frozen=True)
class SuggestionReview:
    """ما يحتاجه المالك ليقرّر اقتراحًا: النص المعتمد الحالي بجوار المقترح، وحالته المشتقة."""

    shared: (
        tuple[str, str, str] | None
    )  # السلوك والشرط والمعيار المعتمدة الآن، أو None إن غاب الهدف من ملف الوحدة
    status: str  # pending أو accepted أو rejected أو applied
    stale: bool  # تغيّر المعتمد بعد كتابة الاقتراح


def suggestion_review(row: ObjectiveSuggestion) -> SuggestionReview:
    """النص المعتمد لهدف الاقتراح من ملف وحدته، و«مُطبَّق» حين يساوي المقبولُ المعتمدَ الحالي."""
    unit = unit_prep(row.lesson.course.slug, row.lesson.unit)
    authored = unit.objectives(row.lesson.code).get(row.example) if unit is not None else None
    if authored is None:
        return SuggestionReview(shared=None, status=row.decision, stale=True)
    shared = (authored.behavior, authored.condition, authored.criterion)
    view = _suggestion_view(row, shared[1:])
    return SuggestionReview(
        shared=shared, status=view["status"], stale=text_digest(shared) != row.base_digest
    )


def blocked_exercises(course: str, lesson: str) -> frozenset[int]:
    """تمارين الدرس التي ربطها آلي لم يُعتمد: لا تدخل ورقة طالب (docs/hybrid_practice_plan.md، قرار 4)."""
    rows = BookExerciseLink.objects.filter(
        lesson__course__slug=course,
        lesson__code=lesson,
        provenance=BookExerciseLink.Provenance.AI_UNREVIEWED,
        reviewed_at__isnull=True,
    )
    return frozenset(rows.values_list("number", flat=True))


def period_package(item: PreparedPeriod, lesson_periods: Iterable[PreparedPeriod]) -> LessonPackage:
    """باقة حصة من تحضيرها. `lesson_periods` حصص الدرس نفسه: منها أهداف أمثلته للحصة الأخيرة."""
    objectives = {
        o.example: " ".join(filter(None, (o.behavior, o.condition)))
        for period in lesson_periods
        for o in period.prep.objectives
    }
    return compose_package(
        item.prep,
        period_items(item.prep),
        objectives=objectives,
        blocked=blocked_exercises(item.prep.course, item.prep.lesson),
    )
