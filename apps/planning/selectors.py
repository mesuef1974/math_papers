"""قراءة: ملف الدرس الشخصي من الفهرس المشتق لمقرره وسير الحصة المبني عليه. حتمي، بلا نص دليل ولا توكنز.

كل قراءة تأخذ المقرر: الرمز «2.6» درس مختلف في كل كتاب. الافتراضي `PLAN_COURSE` هو المقرر الذي تملك المنصة خطته
الفصلية اليوم؛ مسارات العروض تمرّر مقرر الطلب صراحة.
"""

from __future__ import annotations

import hashlib
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Count, QuerySet

from apps.assets.models import Asset
from apps.assets.selectors import asset_bytes
from apps.assets.storage import Storage
from apps.curriculum.courses import GRADE10_SLUG, grade_label
from apps.curriculum.models import Course
from apps.curriculum.selectors import calendar_data, lessons, term_plan_data
from apps.knowledge.domain.course_index import LessonIndex
from apps.knowledge.domain.schemas import lesson_sort_key
from apps.knowledge.domain.unit_prep import approved_standards, unit_prep
from apps.knowledge.selectors import course_index, example_numbers, lesson_index

from .domain.calendar_engine import Closure, Plan, Slot, Term, allocate, parse_terms, sessions
from .domain.deck import Deck, ExampleClip, LessonContent, build_deck
from .domain.feedback import ClassOutcome, Decision, decide
from .domain.plan_periods import PlanPeriod
from .domain.plan_periods import plan_periods as derive_plan_periods
from .domain.prep import PeriodPrep, build_prep, lesson_examples, recall_for
from .domain.prep import allocate as allocate_examples
from .domain.prep_checks import CheckResult, check_lesson, check_prep
from .domain.prep_sheet import PrepSheet, prep_sheet
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
from .models import ClassOutcomeRecord, LessonRunRecord

PLAN_COURSE = GRADE10_SLUG  # المقرر الافتراضي للتخطيط: أول مقرر له خطة فصلية في الجداول


def profile_from_lesson(lesson: LessonIndex) -> LessonProfile:
    """بلوم من أهداف الدرس (غير المصنَّف لا يُحسب) وDOK من صفوف تحليل تمارينه؛ ما لم يُقرأ يبقى فارغًا فلا يُخمَّن."""
    return LessonProfile(
        bloom=frozenset(b for b in lesson.objectives_bloom if b != "unclassified"),
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


def lesson_deck(
    code: str,
    content: LessonContent,
    period_minutes: int = DEFAULT_PERIOD_MINUTES,
    resources: Collection[str] = (),
    course: str = PLAN_COURSE,
) -> Deck:
    """عرض الدرس: الفهرس المشتق وسير الحصة من هنا، والنصوص والمقصوصات من `content` (خارج المستودع)."""
    lesson = _indexed_lesson(code, course)
    flow = build_flow(period_minutes, profile_from_lesson(lesson), resources=resources)
    return build_deck(lesson, content, flow)


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


# ───── عروض الدروس المنشورة من الأصول (المرحلة 4) ─────
DECK_FORMAT = 1  # يُرفع حين يتغير شكل الملف الناتج بلا تغيير في مدخلاته، فيُعاد توليد المخزَّن
DECK_PERIOD_RANGE = (30, 90)
PPTX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def deck_assets(course_slug: str, lesson_code: str) -> list[Asset]:
    """مقاطع أمثلة الدرس المنشورة بترتيب المثال فتتمته."""
    return list(
        Asset.objects.filter(course__slug=course_slug, lesson__code=lesson_code, kind=Asset.Kind.EXAMPLE)
        .select_related("lesson")
        .order_by("number", "part")
    )


def deck_lessons(course_slug: str) -> list[dict]:
    """الدروس التي نُشرت لها مقاطع أمثلة: الرمز والعنوان وعدد الأمثلة (التتمات لا تُعدّ أمثلة)."""
    rows = (
        Asset.objects.filter(course__slug=course_slug, kind=Asset.Kind.EXAMPLE)
        .values("lesson__code", "lesson__title", "lesson__unit")
        .annotate(examples=Count("number", distinct=True), clips=Count("id"))
    )
    lessons = [
        {
            "lesson": r["lesson__code"],
            "title": r["lesson__title"],
            "examples": r["examples"],
            "clips": r["clips"],
        }
        for r in rows
    ]
    return sorted(lessons, key=lambda r: lesson_sort_key(r["lesson"]))


def deck_key(course_slug: str, lesson_code: str, period_minutes: int, assets: Sequence[Asset]) -> str:
    """مفتاح الملف في التخزين: يشتق من كل ما يحدد الناتج (الدرس وعنوانه والزمن وتجزئة كل مقطع وصيغة الملف)،
    فالمدخلات نفسها تعطي المفتاح نفسه ويكون الملف المخزَّن هو الجواب، وتغيّر مقطع أو الزمن يعطي مفتاحًا جديدًا."""
    digest = hashlib.sha256()
    digest.update(f"{DECK_FORMAT}|{course_slug}|{lesson_code}|{period_minutes}".encode())
    for asset in assets:
        digest.update(f"|{asset.lesson.title}|{asset.number}.{asset.part}:{asset.sha256}".encode())
    return f"decks/{course_slug}/{lesson_code}-p{period_minutes}-{digest.hexdigest()[:16]}.pptx"


def clips_of(assets: Sequence[Asset], storage: Storage | None = None) -> tuple[ExampleClip, ...]:
    """مقاطع المخزن كمدخلات عرض: الأصل part=0 يصير جزءًا 1 وتتمته 2 فما فوق."""
    return tuple(
        ExampleClip(
            n=a.number,
            png=asset_bytes(a, storage),
            width_px=a.width,
            height_px=a.height,
            part=a.part + 1,
        )
        for a in assets
    )


@dataclass(frozen=True)
class PreparedPeriod:
    """تحضير حصة من حصص الخطة مع نتائج معاييرها (معايير الحصة ثم معايير درسها)."""

    period: PlanPeriod
    prep: PeriodPrep
    checks: tuple[CheckResult, ...]


def _example_clips(course: str) -> dict[str, dict[int, int]] | None:
    """عدد مقاطع كل مثال (الأصل وتتماته) من فهرس الأصول؛ None إن لم يُنشر للمقرر أصل بعد (فالمقطع معلَّق لا مفقود)."""
    rows = Asset.objects.filter(course__slug=course, kind=Asset.Kind.EXAMPLE)
    if not rows.exists():
        return None
    clips: dict[str, dict[int, int]] = {}
    for code, number in rows.values_list("lesson__code", "number"):
        clips.setdefault(code, {})
        clips[code][number] = clips[code].get(number, 0) + 1
    return clips


def lesson_preps(course: str = PLAN_COURSE) -> tuple[PreparedPeriod, ...]:
    """تحضير كل حصة دروس في الخطة الفصلية بترتيبها، مشتقًّا من الفهرس والخطة والمكتبة، مع معاييره T1 إلى T13."""
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
    out: list[PreparedPeriod] = []
    for position, code in enumerate(order):
        lesson = index[code]
        rows = [p for p in periods if p.lesson == code]
        enrichment = plan.enrichment_examples.get(code, ())
        examples = lesson_examples(
            lesson,
            course,
            enrichment=enrichment,
            generators=generators.get(code, ()),
            clips=None if clips is None else clips.get(code, {}),
        )
        groups = allocate_examples([(e.n, e.weight) for e in examples], len(rows))
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
            )
            checks = check_prep(
                prep,
                by_slug,
                previous_lesson=previous_lesson,
                after_break=after_break,
                quiz_depths=lesson.quiz_depths,
            )
            built.append((period, prep, checks))
        lesson_checks = check_lesson(
            [p for _, p, _ in built], [e.n for e in examples], lesson.standards, enrichment
        )
        out += [PreparedPeriod(period, prep, checks + lesson_checks) for period, prep, checks in built]
    return tuple(out)


class PrepNotFoundError(LookupError):
    """لا مقرر ولا حصة دروس بهذا الرمز في خطته الفصلية."""


def _plan_course(course: str) -> Course:
    found = Course.objects.filter(slug=course, term_plan__isnull=False).first()
    if found is None:
        raise PrepNotFoundError(f"لا خطة فصلية للمقرر {course}")
    return found


def prep_periods(course: str) -> list[dict]:
    """حصص الدروس بترتيب الخطة مع حالة معاييرها: للتنقل في صفحة التحضير."""
    found = _plan_course(course)
    titles = dict(lessons(found).values_list("code", "title"))
    out = []
    for item in lesson_preps(course):
        statuses = {c.status for c in item.checks if c.blocking}
        out.append(
            {
                "lesson": item.prep.lesson,
                "title": titles.get(item.prep.lesson, ""),
                "unit": item.prep.unit,
                "k": item.prep.k,
                "n": item.prep.n,
                "week": item.period.week,
                "status": "fail" if "fail" in statuses else "pending" if "pending" in statuses else "pass",
            }
        )
    return out


def period_sheet(course: str, lesson: str, k: int) -> PrepSheet:
    """ورقة تحضير حصة واحدة (الدرس ورقمها فيه) بنصوصها ومعاييرها."""
    found = _plan_course(course)
    item = next((p for p in lesson_preps(course) if p.prep.lesson == lesson and p.prep.k == k), None)
    if item is None:
        raise PrepNotFoundError(f"لا حصة {k} للدرس {lesson} في خطة {course}")
    title = lessons(found).filter(code=lesson).values_list("title", flat=True).first() or ""
    return prep_sheet(
        item.prep,
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
