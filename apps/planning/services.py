"""خدمات التخطيط: الورقة العلاجية، وسجلات الحصة، والعروض، ونسخة المعلم من أهداف حصته. لا نص كتاب."""

from __future__ import annotations

from datetime import datetime

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from apps.assets.storage import Storage, get_storage
from apps.core.services import record_audit
from apps.curriculum import selectors as curriculum
from apps.curriculum.models import Lesson
from apps.papers import services as papers

from . import selectors
from .domain.calendar_engine import PlanningError
from .domain.deck import DeckError, LessonContent
from .domain.feedback import ClassOutcome, Decision
from .domain.lesson_run import LessonRun
from .domain.objective_text import (
    ObjectiveLockedError,
    ObjectiveNotFoundError,
    ObjectiveTextError,
    clean_note,
    clean_part,
    shared_digest,
)
from .domain.prep import Objective
from .models import ClassOutcomeRecord, LessonRunRecord, ObjectiveOverride, ObjectiveSuggestion, PrepReview
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


# ───── مراجعة المعلم لأهداف حصته (docs/teacher_objective_review_plan.md) ─────


class SuggestionDecidedError(PlanningError):
    """قرار الاقتراح نهائي: لا يُقرَّر مرتين."""


def _target(course: str, lesson: str, example: int | None = None, k: int | None = None) -> str:
    tail = f"/{k}" if k is not None else ""
    return f"{course}/{lesson}{tail}" + (f"#{example}" if example is not None else "")


def _editable_objective(course: str, lesson: str, k: int, example: int) -> Objective:
    """الهدف المعتمد لمثال في الحصة؛ `ObjectiveNotFoundError` إن لم يكن فيها، و`ObjectiveLockedError` قبل اعتماد وحدتها."""
    item = selectors.period_item(course, lesson, k)
    objective = next((o for o in item.prep.objectives if o.example == example), None)
    if objective is None:
        raise ObjectiveNotFoundError(f"لا هدف للمثال {example} في الحصة {k} من الدرس {lesson}")
    if item.prep.unit_status != "approved" or not all(objective.parts):
        raise ObjectiveLockedError(f"أهداف الوحدة {item.prep.unit} لم تُعتمد بعد فلا تُعدَّل")
    return objective


@transaction.atomic
def save_objective(
    owner: AbstractBaseUser,
    course: str,
    lesson: str,
    k: int,
    example: int,
    *,
    condition: str,
    criterion: str,
    suggest: bool = False,
    note: str | None = None,
    request_id: str = "",
) -> None:
    """يحفظ نسخة المعلم من شرط الهدف ومعياره (idempotent). النسخة المساوية للمعتمد تُحذف، ومع `suggest` تُرسَل
    لقطة اقتراح تحل محل اقتراحه المعلّق للمثال نفسه."""
    shared = _editable_objective(course, lesson, k, example)
    condition = clean_part(condition, "الشرط")
    criterion = clean_part(criterion, "المعيار")
    note = clean_note(note)
    record = _lesson(course, lesson)
    key = {"owner": owner, "lesson": record, "example": example}
    previous = ObjectiveOverride.objects.filter(**key).first()
    before = (previous.condition, previous.criterion) if previous else (shared.condition, shared.criterion)
    same_as_shared = (condition, criterion) == (shared.condition, shared.criterion)
    if suggest and same_as_shared:
        raise ObjectiveTextError("الاقتراح يطابق النص المعتمد")
    if same_as_shared:
        ObjectiveOverride.objects.filter(**key).delete()
    else:
        ObjectiveOverride.objects.update_or_create(
            **key,
            defaults={"condition": condition, "criterion": criterion, "base_digest": shared_digest(shared)},
        )
    target = _target(course, lesson, example)
    if before != (condition, criterion):
        record_audit(
            action="prep.objective.save",
            actor=owner,
            target=target,
            payload={"before": list(before), "after": [condition, criterion]},
            request_id=request_id,
        )
    if suggest:
        pending = ObjectiveSuggestion.objects.filter(**key, decision=ObjectiveSuggestion.PENDING).first()
        if pending and (pending.condition, pending.criterion, pending.note) == (condition, criterion, note):
            return
        if pending:
            pending.delete()
        ObjectiveSuggestion.objects.create(
            **key, condition=condition, criterion=criterion, note=note, base_digest=shared_digest(shared)
        )
        record_audit(
            action="prep.objective.suggest",
            actor=owner,
            target=target,
            payload={"condition": condition, "criterion": criterion, "note": note},
            request_id=request_id,
        )


def reset_objective(
    owner: AbstractBaseUser, course: str, lesson: str, k: int, example: int, *, request_id: str = ""
) -> None:
    """يسترجع النص المعتمد بحذف نسخة المعلم (idempotent)؛ اقتراحه المعلّق يبقى."""
    item = selectors.period_item(course, lesson, k)
    if example not in {o.example for o in item.prep.objectives}:
        raise ObjectiveNotFoundError(f"لا هدف للمثال {example} في الحصة {k} من الدرس {lesson}")
    deleted, _ = ObjectiveOverride.objects.filter(
        owner=owner, lesson=_lesson(course, lesson), example=example
    ).delete()
    if deleted:
        record_audit(
            action="prep.objective.reset",
            actor=owner,
            target=_target(course, lesson, example),
            request_id=request_id,
        )


def mark_reviewed(owner: AbstractBaseUser, course: str, lesson: str, k: int, *, request_id: str = "") -> None:
    """علامة «راجعتُ أهداف الحصة» ببصمة نصوصها كما يراها المعلم الآن (idempotent: التكرار يحدّث العلامة)."""
    sheet = selectors.teacher_sheet(course, lesson, k, owner).sheet
    PrepReview.objects.update_or_create(
        owner=owner,
        lesson=_lesson(course, lesson),
        k=k,
        defaults={"digest": selectors.sheet_digest(sheet), "reviewed_at": timezone.now()},
    )
    record_audit(
        action="prep.review", actor=owner, target=_target(course, lesson, k=k), request_id=request_id
    )


@transaction.atomic
def decide_suggestion(
    actor: AbstractBaseUser, suggestion_id: int, decision: str, note: str | None = None
) -> ObjectiveSuggestion:
    """قرار المالك في اقتراح معلم: قبول أو رفض نهائي. القبول لا يكتب ملف الوحدة؛ ذلك أمر
    `apply_objective_suggestions` ثم طلب دمج يعتمده المالك."""
    if not actor.has_perm("planning.decide_objective_suggestion"):
        raise PermissionError("قرار الاقتراحات للمالك وحده")
    if decision not in (ObjectiveSuggestion.ACCEPTED, ObjectiveSuggestion.REJECTED):
        raise PlanningError(f"قرار غير معروف: {decision}")
    row = (
        ObjectiveSuggestion.objects.select_for_update().select_related("lesson__course").get(pk=suggestion_id)
    )
    if row.decision != ObjectiveSuggestion.PENDING:
        raise SuggestionDecidedError(f"الاقتراح {row.pk} قُرِّر من قبل: {row.get_decision_display()}")
    row.decision = decision
    row.decided_by = actor
    row.decided_at = timezone.now()
    row.decision_note = clean_note(note)
    row.save(update_fields=["decision", "decided_by", "decided_at", "decision_note", "updated_at"])
    record_audit(
        action="prep.suggestion.decide",
        actor=actor,
        target=_target(row.lesson.course.slug, row.lesson.code, row.example),
        payload={"suggestion": row.pk, "decision": decision, "note": row.decision_note},
    )
    return row
