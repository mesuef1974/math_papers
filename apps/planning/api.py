"""عروض الدروس للمعلم المسجَّل (خلف `TeacherAuth`).

- GET  /decks/periods?course=        حصص الدروس بحالة معاييرها وجاهزية مقاطع أمثلتها
- POST /decks/                       يطلب بناء عرض حصة (مهمة خلفية) ويعيد حالته
- GET  /decks/status?course=&lesson=&k=   الحالة: pending | ready | failed
- GET  /decks/download?course=&lesson=&k= ملف PPTX الجاهز
- GET  /preps/<مقرر>                 حصص الدروس بترتيب الخطة وحالة معاييرها
- GET  /preps/<مقرر>/<درس>/<k>       تحضير الحصة بنصوصه ومعاييره
- GET  /preps/<مقرر>/<درس>/<k>/word  التحضير في Word بنموذج الوزارة (بنسخة المعلم من أهدافه)
- PUT  /preps/<مقرر>/<درس>/<k>/objectives/<مثال>  نسخة المعلم من شرط الهدف ومعياره، واقتراحها اختياريًا
- DELETE /preps/<مقرر>/<درس>/<k>/objectives/<مثال>  استرجاع النص المعتمد
- POST /preps/<مقرر>/<درس>/<k>/review  علامة «راجعتُ أهداف الحصة»
- PUT  /preps/<مقرر>/<درس>/<k>/override  تعديل المعلم لحصص الدرس (التوزيع والاستراتيجيات والتمارين المحذوفة)، له وحده
- DELETE /preps/<مقرر>/<درس>/<k>/override  استرجاع التحضير المشترك للدرس
- POST /results/<مقرر>/<درس>          نتائج طلاب شعبة في بنود الدرس دفعة واحدة (idempotent؛ نوع الخطأ من بنك البنود)
- GET  /results/<مقرر>/<درس>?section=  نتائج شعبة من شعب المعلم وأعداد أخطائها بالنوع؛ 403 لشعبة ليست له
- GET  /results/sections              شعب المعلم (ما له فيه طلاب)
- GET  /misconceptions/<مقرر>/<درس>?section=  لوحة سوء الفهم: طلاب كل نوع خطأ في شعبة المعلم؛ 403 لشعبة ليست له
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime

from django.http import HttpRequest, HttpResponse
from ninja import Field, Query, Router, Schema
from ninja.errors import HttpError
from ninja.throttling import UserRateThrottle

from apps.assets.storage import StorageError, get_storage
from apps.core.middleware import request_id_of
from apps.core.services import record_audit
from apps.papers.access import TeacherAuth
from apps.papers.domain.item_bank import OPTION_COUNT

from . import selectors, services
from .domain.calendar_engine import PlanningError
from .domain.deck import DeckError
from .domain.item_results import MAX_ENTRIES, MAX_EXAMPLE, MAX_SEED, Entry, ResultsError
from .domain.objective_text import ObjectiveLockedError, ObjectiveNotFoundError, ObjectiveTextError
from .domain.prep_override import OverrideError
from .prep_word import DOCX_CONTENT_TYPE, prep_docx, prep_filename
from .tasks import build_period_deck_task

logger = logging.getLogger(__name__)
router = Router(tags=["العروض"], auth=TeacherAuth(), throttle=[UserRateThrottle()])


class PrepPeriodOut(Schema):
    lesson: str
    title: str
    unit: int
    k: int
    n: int
    week: int
    status: str
    customized: bool = False
    kind: str = "lesson"  # أو نوع حصة غير الدرس: orientation | quiz | review | exam | project | support


class DeckPeriodOut(PrepPeriodOut):
    examples: int
    clips: bool
    stale: bool


class DeckRequest(Schema):
    course: str
    lesson: str
    k: int = Field(ge=1)


class DeckOut(Schema):
    status: str
    detail: str = ""
    filename: str


def _prepare(request: HttpRequest, course: str, lesson: str, k: int) -> str:
    try:
        return services.prepare_deck(course, lesson, k, request.user)
    except selectors.PrepNotFoundError as error:
        raise HttpError(404, str(error)) from error
    except DeckError as error:
        raise HttpError(422, str(error)) from error


def _filename(course: str, lesson: str, key: str) -> str:
    """اسم الملف من مفتاحه: المقرر والدرس ورقم الحصة من عددها (`…-k2of3-…`)."""
    period = key.rsplit("/", 1)[-1].split("-")[1]
    return f"{course}-lesson-{lesson}-{period}.pptx"


@router.get("decks/periods", response=list[DeckPeriodOut])
def deck_periods(request: HttpRequest, course: str):
    try:
        return selectors.deck_periods(course, request.user)
    except selectors.PrepNotFoundError as error:
        raise HttpError(404, str(error)) from error


@router.post("decks/", response=DeckOut)
def request_deck(request: HttpRequest, payload: DeckRequest):
    key = _prepare(request, payload.course, payload.lesson, payload.k)
    services.record_deck_build(request.user, payload.course, payload.lesson, payload.k, key)
    state, detail = services.deck_state(key)
    if state != "ready":
        if state == "failed":
            services.clear_deck_failure(key)
        try:
            build_period_deck_task.delay(payload.course, payload.lesson, payload.k, request.user.pk)
        except Exception:  # الوضع الفوري يرفع هنا؛ الفشل مسجَّل في التخزين فيقرؤه الرد
            logger.exception("فشل بناء عرض %s", key)
        state, detail = services.deck_state(key)  # الوضع الفوري (تطوير واختبار) ينتهي هنا جاهزًا
    record_audit(
        action="decks.request",
        actor=request.user,
        target=key,
        payload={"course": payload.course, "lesson": payload.lesson, "k": payload.k},
        request_id=request_id_of(request),
    )
    return {"status": state, "detail": detail, "filename": _filename(payload.course, payload.lesson, key)}


@router.get("decks/status", response=DeckOut)
def deck_status(request: HttpRequest, filters: Query[DeckRequest]):
    key = _prepare(request, filters.course, filters.lesson, filters.k)
    state, detail = services.deck_state(key)
    return {"status": state, "detail": detail, "filename": _filename(filters.course, filters.lesson, key)}


@router.get("decks/download")
def download(request: HttpRequest, filters: Query[DeckRequest]):
    key = _prepare(request, filters.course, filters.lesson, filters.k)
    try:
        data = get_storage().get(key)
    except StorageError as error:
        raise HttpError(404, "العرض غير جاهز بعد: اطلب بناءه أولًا") from error
    record_audit(
        action="decks.download",
        actor=request.user,
        target=key,
        request_id=request_id_of(request),
    )
    response = HttpResponse(data, content_type=selectors.PPTX_CONTENT_TYPE)
    response["Content-Disposition"] = (
        f'attachment; filename="{_filename(filters.course, filters.lesson, key)}"'
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class SharedObjectiveOut(Schema):
    behavior: str
    condition: str
    criterion: str


class MyObjectiveOut(Schema):
    condition: str
    criterion: str


class SuggestionOut(Schema):
    status: str  # pending | accepted | rejected | applied
    condition: str
    criterion: str
    note: str
    created_at: datetime


class ObjectiveOut(Schema):
    example: int | None
    text: str
    pending: bool
    shared: SharedObjectiveOut | None = None
    mine: MyObjectiveOut | None = None
    stale: bool = False
    editable: bool = False
    suggestion: SuggestionOut | None = None
    teach_activity: str
    teach_assessment: str
    teach_minutes: int
    check_activity: str
    check_assessment: str
    check_minutes: int


class StageOut(Schema):
    name: str
    label: str
    minutes: int
    strategy: str


class CheckOut(Schema):
    code: str
    title: str
    status: str
    kind: str
    details: list[str]


class ReviewOut(Schema):
    reviewed_at: datetime
    stale: bool


class StrategyOptionOut(Schema):
    slug: str
    title: str


class StageEditOut(Schema):
    name: str
    current: str
    chosen: str | None
    options: list[StrategyOptionOut]


class PrepEditOut(Schema):
    """ما تعرضه واجهة تعديل الحصة (`selectors.prep_edit`)."""

    state: str
    allocation: list[list[int]]
    default_allocation: list[list[int]]
    stages: list[StageEditOut]
    exercises: list[int]
    removed: list[int]


class PaperLinkOut(Schema):
    """ورقة يولّدها «أوراق» لحصة غير درس (`non_lesson.PaperLink`): تفتح صفحة التوليد بمدخلاتها."""

    kind: str
    label: str
    lessons: list[str]
    level: str
    blueprint: str


class PrepOut(Schema):
    course: str
    lesson: str
    lesson_title: str
    unit: int
    k: int
    n: int
    week: int
    minutes: int
    year: str
    semester: str
    grade: str
    day_date: str
    outcomes: str
    main_sources: str
    support_sources: str
    warmup: str
    warmup_minutes: int
    objectives: list[ObjectiveOut]
    closing: str
    closing_minutes: int
    homework: str
    basic: str
    advanced: str
    quiz: str
    stages: list[StageOut]
    checks: list[CheckOut]
    pending: bool
    review: ReviewOut | None = None
    edit: PrepEditOut | None = None  # حصة غير الدرس مشتركة بلا تعديل
    kind: str = "lesson"
    papers: list[PaperLinkOut] = []
    scope: list[str] = []


class PrepOverrideIn(Schema):
    """تعديل المعلم للحصة `k`: استراتيجيات مراحلها وتمارينها المحذوفة تحل محل المحفوظ لها، والتوزيع (إن أُرسل) لحصص الدرس كلها.
    المخطط القانوني وقواعده في `domain/prep_override.py`."""

    allocation: list[list[int]] | None = Field(default=None, max_length=8)
    strategies: dict[str, str] = Field(default_factory=dict, max_length=6)
    removed: list[int] = Field(default_factory=list, max_length=40)


class ObjectiveIn(Schema):
    condition: str = Field(max_length=2000)
    criterion: str = Field(max_length=2000)
    suggest: bool = False
    note: str | None = Field(default=None, max_length=2000)


def _teacher_sheet(request: HttpRequest, course: str, lesson: str, k: int) -> selectors.TeacherSheet:
    try:
        return selectors.teacher_sheet(course, lesson, k, request.user)
    except selectors.PrepNotFoundError as error:
        raise HttpError(404, str(error)) from error


def _prep_out(view: selectors.TeacherSheet) -> dict:
    """ورقة الحصة بنسخة المعلم، ولكل هدف حاله (المعتمد ونسخته وقِدمها واقتراحه)، وعلامة المراجعة."""
    data = asdict(view.sheet)
    data["pending"] = view.sheet.pending
    for row in data["objectives"]:
        state = view.objectives.get(row["example"])
        if state is not None:
            row.update(asdict(state))
    data["review"] = view.review
    data["edit"] = view.edit or None
    return data


@contextmanager
def _objective_errors():
    try:
        yield
    except (selectors.PrepNotFoundError, ObjectiveNotFoundError) as error:
        raise HttpError(404, str(error)) from error
    except ObjectiveLockedError as error:
        raise HttpError(409, str(error)) from error
    except (ObjectiveTextError, OverrideError) as error:
        raise HttpError(422, str(error)) from error


@router.get("preps/{course}", response=list[PrepPeriodOut])
def prep_periods(request: HttpRequest, course: str):
    try:
        return selectors.prep_periods(course, request.user)
    except selectors.PrepNotFoundError as error:
        raise HttpError(404, str(error)) from error


@router.get("preps/{course}/{lesson}/{k}", response=PrepOut)
def prep(request: HttpRequest, course: str, lesson: str, k: int):
    return _prep_out(_teacher_sheet(request, course, lesson, k))


@router.put("preps/{course}/{lesson}/{k}/objectives/{example}", response=PrepOut)
def save_objective(
    request: HttpRequest, course: str, lesson: str, k: int, example: int, payload: ObjectiveIn
):
    with _objective_errors():
        services.save_objective(
            request.user,
            course,
            lesson,
            k,
            example,
            condition=payload.condition,
            criterion=payload.criterion,
            suggest=payload.suggest,
            note=payload.note,
            request_id=request_id_of(request),
        )
    return _prep_out(_teacher_sheet(request, course, lesson, k))


@router.delete("preps/{course}/{lesson}/{k}/objectives/{example}", response=PrepOut)
def reset_objective(request: HttpRequest, course: str, lesson: str, k: int, example: int):
    with _objective_errors():
        services.reset_objective(request.user, course, lesson, k, example, request_id=request_id_of(request))
    return _prep_out(_teacher_sheet(request, course, lesson, k))


@router.put("preps/{course}/{lesson}/{k}/override", response=PrepOut)
def save_override(request: HttpRequest, course: str, lesson: str, k: int, payload: PrepOverrideIn):
    """يحفظ تعديل المعلم للحصة `k` (وتوزيع أمثلة الدرس إن أُرسل) ويعيد ورقة الحصة بعده."""
    with _objective_errors():
        services.save_period_override(
            request.user,
            course,
            lesson,
            k,
            allocation=payload.allocation,
            strategies=payload.strategies,
            removed=payload.removed,
            request_id=request_id_of(request),
        )
    return _prep_out(_teacher_sheet(request, course, lesson, k))


@router.delete("preps/{course}/{lesson}/{k}/override", response=PrepOut)
def reset_override(request: HttpRequest, course: str, lesson: str, k: int):
    with _objective_errors():
        services.reset_prep_override(request.user, course, lesson, request_id=request_id_of(request))
    return _prep_out(_teacher_sheet(request, course, lesson, k))


@router.post("preps/{course}/{lesson}/{k}/review", response=PrepOut)
def review_prep(request: HttpRequest, course: str, lesson: str, k: int):
    with _objective_errors():
        services.mark_reviewed(request.user, course, lesson, k, request_id=request_id_of(request))
    return _prep_out(_teacher_sheet(request, course, lesson, k))


# ───── تشخيص الخطأ: نتيجة الطالب لكل بند (قرار المالك 2026-11-25) ─────


class ItemResultIn(Schema):
    """اختيار طالب في بند. لا حقل للصحة ولا لنوع الخطأ: يُشتقان من بنك البنود في الخادم."""

    enrollment_no: str = Field(max_length=40)
    first_name: str = Field(max_length=120)
    last_name: str = Field(max_length=120)
    example: int = Field(ge=1, le=MAX_EXAMPLE)
    seed: int = Field(ge=0, le=MAX_SEED)
    choice: int = Field(ge=0, lt=OPTION_COUNT)


class SectionResultsIn(Schema):
    section: str = Field(max_length=40)
    results: list[ItemResultIn] = Field(min_length=1, max_length=MAX_ENTRIES)


class ResultsSavedOut(Schema):
    students: int
    results: int
    created: int
    updated: int


class ItemResultOut(Schema):
    example: int
    seed: int
    choice: int
    correct: bool
    error_kind: str | None
    misconception: str | None


class StudentResultsOut(Schema):
    enrollment_no: str
    first_name: str
    last_name: str
    results: list[ItemResultOut]


class ErrorKindOut(Schema):
    kind: str
    label: str
    count: int


class SectionResultsOut(Schema):
    course: str
    lesson: str
    section: str
    attempted: int
    correct: int
    kinds: list[ErrorKindOut]
    students: list[StudentResultsOut]


@router.post("results/{course}/{lesson}", response=ResultsSavedOut)
def record_results(request: HttpRequest, course: str, lesson: str, payload: SectionResultsIn):
    """نتائج شعبة المعلم في بنود درس دفعة واحدة (idempotent)."""
    try:
        return services.record_item_results(
            request.user,
            course,
            lesson,
            payload.section,
            [Entry(**row.dict()) for row in payload.results],
            request_id=request_id_of(request),
        )
    except ResultsError as error:
        raise HttpError(422, str(error)) from error
    except PlanningError as error:  # مقرر أو درس مجهول، أو شعبة بلا اسم
        raise HttpError(404, str(error)) from error


def _read_section(
    request: HttpRequest, response: HttpResponse, scope: str, read, counts, *where: str
) -> dict:
    """قراءة بيانات شعبة في درس: 403 لشعبة ليست للمعلم و404 لدرس مجهول، وكل قراءة وكل رفض في سجل التدقيق بالأعداد
    وحدها (`counts`) بلا أسماء ولا أرقام قيد، والرد لا يُخزَّن."""
    course, lesson, section = where
    target = services.results_target(course, lesson, section.strip()[:40])
    try:
        data = read(request.user, course, lesson, section)
    except selectors.SectionNotOwnedError as error:
        record_audit(
            action=f"{scope}.denied", actor=request.user, target=target, request_id=request_id_of(request)
        )
        raise HttpError(403, "الشعبة ليست من شعبك") from error
    except selectors.ResultsNotFoundError as error:
        raise HttpError(404, str(error)) from error
    record_audit(
        action=f"{scope}.read",
        actor=request.user,
        target=target,
        payload=counts(data),
        request_id=request_id_of(request),
    )
    response["Cache-Control"] = "private, no-store"
    return data


@router.get("results/sections", response=list[str])
def result_sections(request: HttpRequest):
    """شعب المعلم: ما أدخل فيه طلابًا."""
    return selectors.owned_sections(request.user)


@router.get("results/{course}/{lesson}", response=SectionResultsOut)
def section_results(request: HttpRequest, response: HttpResponse, course: str, lesson: str, section: str):
    """نتائج شعبة من شعب المعلم في درس؛ 403 لشعبة ليست له. كل قراءة وكل رفض في سجل التدقيق بلا أسماء."""
    return _read_section(
        request,
        response,
        "results",
        selectors.section_results,
        lambda data: {"students": len(data["students"]), "results": data["attempted"]},
        course,
        lesson,
        section,
    )


class BoardStudentOut(Schema):
    enrollment_no: str
    first_name: str
    last_name: str
    examples: list[int]


class BoardKindOut(Schema):
    kind: str
    label: str
    count: int
    examples: list[int]
    students: list[BoardStudentOut]


class MisconceptionBoardOut(Schema):
    course: str
    lesson: str
    section: str
    students: int
    entered: int
    correct: int
    missing: int
    kinds: list[BoardKindOut]


@router.get("misconceptions/{course}/{lesson}", response=MisconceptionBoardOut)
def misconception_board(request: HttpRequest, response: HttpResponse, course: str, lesson: str, section: str):
    """لوحة سوء الفهم لشعبة من شعب المعلم في درس؛ 403 لشعبة ليست له. السجل أعداد كل نوع بلا أسماء."""
    return _read_section(
        request,
        response,
        "misconceptions",
        selectors.misconception_board,
        lambda data: {
            "students": data["students"],
            "entered": data["entered"],
            "correct": data["correct"],
            "kinds": {kind["kind"]: kind["count"] for kind in data["kinds"]},
        },
        course,
        lesson,
        section,
    )


@router.get("preps/{course}/{lesson}/{k}/word")
def prep_word(request: HttpRequest, course: str, lesson: str, k: int):
    sheet = _teacher_sheet(request, course, lesson, k).sheet
    user = request.user
    data = prep_docx(sheet, teacher=user.get_full_name() or user.get_username())
    record_audit(
        action="preps.word",
        actor=user,
        target=f"{course}/{lesson}/{k}",
        request_id=request_id_of(request),
    )
    response = HttpResponse(data, content_type=DOCX_CONTENT_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{prep_filename(sheet)}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
