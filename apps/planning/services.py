"""جسر قرار ما بعد الحصة إلى الأوراق: ورقة علاجية من مولّدات الدرس نفسه. لا نص كتاب ولا توكنز."""

from __future__ import annotations

from datetime import datetime

from django.contrib.auth.models import AbstractBaseUser

from apps.assets.storage import Storage, get_storage
from apps.curriculum import selectors as curriculum
from apps.curriculum.models import Lesson
from apps.papers import services as papers

from . import selectors
from .domain.calendar_engine import PlanningError
from .domain.deck import DeckError, LessonContent
from .domain.feedback import ClassOutcome, Decision
from .domain.lesson_run import LessonRun
from .models import ClassOutcomeRecord, LessonRunRecord
from .pptx_export import build_pptx

REMEDIAL_PER_PERIOD = 5  # أسئلة لكل حصة إعادة تدريس؛ المراجعة السريعة بلا حصة تأخذ حصة واحدة في الحساب


def remedial_worksheet(decision: Decision, seed: int | None = None) -> dict | None:
    """ورقة علاجية (مستوى سهل) للدرس بحسب القرار؛ لا ورقة عند التقدّم. الدرس المجهول يرفع `UnknownLessonError`."""
    if decision.action == "advance":
        return None
    count = REMEDIAL_PER_PERIOD * max(decision.extra_periods, 1)
    return papers.build_worksheet(decision.lesson_id, count, seed, purpose="remedial")


def _section(value: str) -> str:
    section = value.strip()
    if not section or len(section) > 20:
        raise PlanningError("الشعبة مطلوبة وبحد أقصى 20 حرفًا")
    return section


def _lesson(course: str, code: str) -> Lesson:
    """درس السجل في مقرره؛ الرمز وحده لا يكفي فهو يتكرر بين الكتب."""
    try:
        lesson = curriculum.lessons(curriculum.course_by_slug(course)).filter(code=code).first()
    except curriculum.UnknownCourseError as error:
        raise PlanningError(f"المقرر غير موجود: {course}") from error
    if lesson is None:
        raise PlanningError(f"الدرس {code} غير موجود في المقرر {course}")
    return lesson


def record_outcome(
    owner: AbstractBaseUser, section: str, outcome: ClassOutcome, course: str = selectors.PLAN_COURSE
) -> tuple[ClassOutcomeRecord, bool]:
    """يحفظ آخر نتيجة لشعبة في درس من مقرر؛ idempotent: التكرار يحدّث السجل نفسه ولا يضاعفه."""
    return ClassOutcomeRecord.objects.update_or_create(
        owner=owner,
        section=_section(section),
        lesson=_lesson(course, outcome.lesson_id),
        defaults={
            "lesson_code": outcome.lesson_id,
            "attempted": outcome.attempted,
            "correct": outcome.correct,
            "pace": outcome.pace,
            "obstacles": sorted(outcome.obstacles),
        },
    )


def save_run_report(
    owner: AbstractBaseUser,
    section: str,
    lesson_code: str,
    run: LessonRun,
    started_at: datetime,
    course: str = selectors.PLAN_COURSE,
) -> tuple[LessonRunRecord, bool]:
    """يحفظ تقرير حصة (المخطط مقابل الفعلي لكل طور)؛ المفتاح بداية الحصة فتكرار الحفظ لا يضاعف التقرير."""
    return LessonRunRecord.objects.update_or_create(
        owner=owner,
        section=_section(section),
        lesson=_lesson(course, lesson_code),
        started_at=started_at,
        defaults={
            "lesson_code": lesson_code,
            "period_minutes": run.flow.period_minutes,
            "finished": run.finished,
            "phases": [
                {"phase": c.phase, "planned": c.planned, "actual": round(c.actual, 2), "skipped": c.skipped}
                for c in run.closed
            ],
        },
    )


# ───── توليد عرض الدرس من الأصول المنشورة (المرحلة 4) ─────
def _error_key(key: str) -> str:
    return f"{key}.error"


def prepare_deck(course_slug: str, lesson_code: str, period_minutes: int) -> str:
    """يتحقق من الطلب ويعيد مفتاح الملف في التخزين؛ كل رفض `DeckError` برسالة عربية. لا يكتب شيئًا."""
    low, high = selectors.DECK_PERIOD_RANGE
    if not low <= period_minutes <= high:
        raise DeckError(f"زمن الحصة بين {low} و{high} دقيقة")
    assets = selectors.deck_assets(course_slug, lesson_code)
    if not assets:
        raise DeckError(f"لا مقاطع أمثلة منشورة للدرس {lesson_code} في المقرر {course_slug}")
    try:
        # يفشل مبكرًا إن غاب الدرس من فهرس مقرره أو استحال توزيع الزمن
        selectors.lesson_flow(lesson_code, period_minutes, course=course_slug)
    except KeyError as error:
        raise DeckError(f"الدرس {lesson_code} غير موجود في فهرس المقرر") from error
    except PlanningError as error:
        raise DeckError(str(error)) from error
    return selectors.deck_key(course_slug, lesson_code, period_minutes, assets)


def deck_state(key: str, storage: Storage | None = None) -> tuple[str, str]:
    """حالة التوليد من التخزين وحده: (ready, "") أو (failed, سبب) أو (pending, ""). بلا جدول مهام فتصمد لإعادة تشغيل العامل."""
    storage = storage or get_storage()
    if storage.exists(key):
        return "ready", ""
    if storage.exists(_error_key(key)):
        return "failed", storage.get(_error_key(key)).decode("utf-8")
    return "pending", ""


def build_lesson_deck(
    course_slug: str, lesson_code: str, period_minutes: int, storage: Storage | None = None
) -> str:
    """يبني ملف PPTX للدرس ويضعه في التخزين تحت مفتاحه المشتق؛ idempotent: الملف الموجود لا يُعاد بناؤه.

    الدرس وأمثلته المقصوصة من التخزين والفهرس المشتق وحدهما: لا أهداف ولا مصطلحات (نص الدليل لا يصعد إلى الإنتاج)."""
    storage = storage or get_storage()
    key = prepare_deck(course_slug, lesson_code, period_minutes)
    if storage.exists(key):
        return key
    assets = selectors.deck_assets(course_slug, lesson_code)
    try:
        content = LessonContent(title=assets[0].lesson.title, examples=selectors.clips_of(assets, storage))
        deck = selectors.lesson_deck(lesson_code, content, period_minutes, course=course_slug)
        data = build_pptx(deck)
    except Exception as error:
        message = str(error) if isinstance(error, PlanningError) else "تعذّر بناء العرض"
        storage.put(_error_key(key), message.encode("utf-8"), "text/plain; charset=utf-8")
        raise
    storage.put(key, data, selectors.PPTX_CONTENT_TYPE)
    if storage.exists(_error_key(key)):
        storage.delete(_error_key(key))
    return key


def clear_deck_failure(key: str, storage: Storage | None = None) -> None:
    """يمحو أثر فشل سابق قبل إعادة المحاولة فلا تبقى الحالة «failed» أثناء المحاولة الجديدة."""
    storage = storage or get_storage()
    if storage.exists(_error_key(key)):
        storage.delete(_error_key(key))
