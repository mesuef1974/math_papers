"""قراءة: ملف الدرس الشخصي من فهرس العاشر المشتق وسير الحصة المبني عليه. حتمي، بلا نص دليل ولا توكنز."""

from __future__ import annotations

import hashlib
from collections.abc import Collection, Sequence

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Count, QuerySet

from apps.assets.models import Asset
from apps.assets.selectors import asset_bytes
from apps.assets.storage import Storage
from apps.knowledge.domain.grade10_index import Grade10Lesson
from apps.knowledge.selectors import grade10_index, grade10_lesson

from .domain.calendar_engine import Closure, Plan, Slot, allocate, load_terms, sessions
from .domain.deck import Deck, ExampleClip, LessonContent, build_deck
from .domain.feedback import ClassOutcome, Decision, decide
from .domain.semester_plan import (
    TermPlan,
    check_catalog,
    load_term_plan,
    ministry_slots,
    plan_items,
    term_for_plan,
)
from .domain.strategies import (
    DEFAULT_PERIOD_MINUTES,
    Flow,
    LessonProfile,
    build_flow,
)
from .models import ClassOutcomeRecord, LessonRunRecord


def profile_from_lesson(lesson: Grade10Lesson) -> LessonProfile:
    """بلوم من أهداف الدرس (غير المصنَّف لا يُحسب) وDOK من صفوف تحليل تمارينه؛ ما لم يُقرأ يبقى فارغًا فلا يُخمَّن."""
    return LessonProfile(
        bloom=frozenset(b for b in lesson.objectives_bloom if b != "unclassified"),
        dok=frozenset(row.dok for row in lesson.analysis),
    )


def lesson_profile(code: str) -> LessonProfile:
    lesson = grade10_lesson(code)
    if lesson is None:
        raise KeyError(f"درس غير موجود في الفهرس: {code}")
    return profile_from_lesson(lesson)


def lesson_flow(
    code: str,
    period_minutes: int = DEFAULT_PERIOD_MINUTES,
    resources: Collection[str] = (),
) -> Flow:
    return build_flow(period_minutes, lesson_profile(code), resources=resources)


def lesson_codes() -> list[str]:
    return [lesson.lesson for lesson in grade10_index().lessons]


def outcome_records(owner: AbstractBaseUser, section: str | None = None) -> QuerySet[ClassOutcomeRecord]:
    rows = ClassOutcomeRecord.objects.filter(owner=owner)
    return rows.filter(section=section) if section else rows


def outcome_of(record: ClassOutcomeRecord) -> ClassOutcome:
    return ClassOutcome(
        record.lesson_code, record.attempted, record.correct, record.pace, frozenset(record.obstacles)
    )


def decision_of(record: ClassOutcomeRecord) -> Decision:
    """القرار يُشتق دائمًا من السجل بالعتبات الحالية ولا يُخزَّن، فتعديل العتبات يسري على النتائج المحفوظة."""
    return decide(outcome_of(record))


def run_reports(owner: AbstractBaseUser, section: str | None = None) -> QuerySet[LessonRunRecord]:
    rows = LessonRunRecord.objects.filter(owner=owner)
    return rows.filter(section=section) if section else rows


def lesson_deck(
    code: str,
    content: LessonContent,
    period_minutes: int = DEFAULT_PERIOD_MINUTES,
    resources: Collection[str] = (),
) -> Deck:
    """عرض الدرس: الفهرس المشتق وسير الحصة من هنا، والنصوص والمقصوصات من `content` (خارج المستودع)."""
    lesson = grade10_lesson(code)
    if lesson is None:
        raise KeyError(f"درس غير موجود في الفهرس: {code}")
    flow = build_flow(period_minutes, profile_from_lesson(lesson), resources=resources)
    return build_deck(lesson, content, flow)


def term_plan() -> TermPlan:
    """خطة الفصل الأول للوزارة بعد مطابقة دروسها وأمثلتها الإثرائية على الفهرس المشتق."""
    plan = load_term_plan()
    index = grade10_index()
    check_catalog(
        plan,
        [lesson.lesson for lesson in index.lessons],
        {lesson.lesson: [e.n for e in lesson.examples] for lesson in index.lessons},
    )
    return plan


def term1_schedule(slots: Collection[Slot] | None = None) -> tuple[TermPlan, list, Plan]:
    """توزيع بنود الوزارة على حصص شعبة (الافتراضي خمس حصص أسبوعيًا): الخطة والبنود وما وضعه المحرك."""
    plan = term_plan()
    term = term_for_plan(load_terms()[plan.term_id], plan)
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
    return sorted(lessons, key=lambda r: [int(p) for p in r["lesson"].split(".")])


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
