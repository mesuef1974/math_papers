"""عروض الدروس للمعلم المسجَّل (خلف `TeacherAuth`).

- GET  /decks/lessons?course=        الدروس التي نُشرت لها مقاطع أمثلة
- POST /decks/                       يطلب بناء عرض (مهمة خلفية) ويعيد حالته ومفتاحه
- GET  /decks/status?course=&lesson= الحالة: pending | ready | failed
- GET  /decks/download?course=&lesson=  ملف PPTX الجاهز
- GET  /preps/<مقرر>                 حصص الدروس بترتيب الخطة وحالة معاييرها
- GET  /preps/<مقرر>/<درس>/<k>       تحضير الحصة بنصوصه ومعاييره
- GET  /preps/<مقرر>/<درس>/<k>/word  التحضير في Word بنموذج الوزارة
"""

from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponse
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from ninja.throttling import UserRateThrottle

from apps.assets.storage import StorageError, get_storage
from apps.core.middleware import request_id_of
from apps.core.services import record_audit
from apps.papers.access import TeacherAuth

from . import selectors, services
from .domain.deck import DeckError
from .domain.strategies import DEFAULT_PERIOD_MINUTES
from .prep_word import DOCX_CONTENT_TYPE, prep_docx, prep_filename
from .tasks import build_lesson_deck_task

logger = logging.getLogger(__name__)
router = Router(tags=["العروض"], auth=TeacherAuth(), throttle=[UserRateThrottle()])


class DeckLessonOut(Schema):
    lesson: str
    title: str
    examples: int
    clips: int


class DeckRequest(Schema):
    course: str
    lesson: str
    period_minutes: int = DEFAULT_PERIOD_MINUTES


class DeckQuery(Schema):
    course: str
    lesson: str
    period_minutes: int = DEFAULT_PERIOD_MINUTES


class DeckOut(Schema):
    status: str
    detail: str = ""
    filename: str


def _prepare(course: str, lesson: str, period: int) -> str:
    try:
        return services.prepare_deck(course, lesson, period)
    except DeckError as error:
        raise HttpError(422, str(error)) from error


def _filename(course: str, lesson: str) -> str:
    return f"{course}-lesson-{lesson}.pptx"


@router.get("decks/lessons", response=list[DeckLessonOut])
def lessons(request: HttpRequest, course: str):
    return selectors.deck_lessons(course)


@router.post("decks/", response=DeckOut)
def request_deck(request: HttpRequest, payload: DeckRequest):
    key = _prepare(payload.course, payload.lesson, payload.period_minutes)
    state, detail = services.deck_state(key)
    if state != "ready":
        if state == "failed":
            services.clear_deck_failure(key)
        try:
            build_lesson_deck_task.delay(payload.course, payload.lesson, payload.period_minutes)
        except Exception:  # الوضع الفوري يرفع هنا؛ الفشل مسجَّل في التخزين فيقرؤه الرد
            logger.exception("فشل بناء عرض %s", key)
        state, detail = services.deck_state(key)  # الوضع الفوري (تطوير واختبار) ينتهي هنا جاهزًا
    record_audit(
        action="decks.request",
        actor=request.user,
        target=key,
        payload={"course": payload.course, "lesson": payload.lesson, "period": payload.period_minutes},
        request_id=request_id_of(request),
    )
    return {"status": state, "detail": detail, "filename": _filename(payload.course, payload.lesson)}


@router.get("decks/status", response=DeckOut)
def deck_status(request: HttpRequest, filters: Query[DeckQuery]):
    key = _prepare(filters.course, filters.lesson, filters.period_minutes)
    state, detail = services.deck_state(key)
    return {"status": state, "detail": detail, "filename": _filename(filters.course, filters.lesson)}


@router.get("decks/download")
def download(request: HttpRequest, filters: Query[DeckQuery]):
    key = _prepare(filters.course, filters.lesson, filters.period_minutes)
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
    response["Content-Disposition"] = f'attachment; filename="{_filename(filters.course, filters.lesson)}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class PrepPeriodOut(Schema):
    lesson: str
    title: str
    unit: int
    k: int
    n: int
    week: int
    status: str


class ObjectiveOut(Schema):
    example: int | None
    text: str
    pending: bool
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


def _sheet(course: str, lesson: str, k: int):
    try:
        return selectors.period_sheet(course, lesson, k)
    except selectors.PrepNotFoundError as error:
        raise HttpError(404, str(error)) from error


@router.get("preps/{course}", response=list[PrepPeriodOut])
def prep_periods(request: HttpRequest, course: str):
    try:
        return selectors.prep_periods(course)
    except selectors.PrepNotFoundError as error:
        raise HttpError(404, str(error)) from error


@router.get("preps/{course}/{lesson}/{k}", response=PrepOut)
def prep(request: HttpRequest, course: str, lesson: str, k: int):
    return _sheet(course, lesson, k)


@router.get("preps/{course}/{lesson}/{k}/word")
def prep_word(request: HttpRequest, course: str, lesson: str, k: int):
    sheet = _sheet(course, lesson, k)
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
