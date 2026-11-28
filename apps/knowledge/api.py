"""مراجعة ربط تمارين الكتاب بأمثلتها: للمشرف العام وحده، فالربط مشترك بين كل المعلمين.

- GET  /exercise-links/<مقرر>                       دروس المقرر وعدد ما لم يُعتمد
- GET  /exercise-links/<مقرر>/<درس>                 أمثلة الدرس وتمارينه المربوطة
- PUT  /exercise-links/<مقرر>/<درس>/<نوع>/<رقم>     اعتماد أمثلة تمرين (كما هي أو مصحَّحة)
- POST /exercise-links/<مقرر>/<درس>/approve         اعتماد كل ما لم يُعتمد في الدرس
"""

from __future__ import annotations

from typing import Literal

from django.http import HttpRequest
from ninja import Field, Router, Schema
from ninja.errors import HttpError
from ninja.security import django_auth
from ninja.throttling import UserRateThrottle

from apps.core.middleware import request_id_of

from . import selectors, services

router = Router(tags=["ربط التمارين"], auth=django_auth, throttle=[UserRateThrottle()])


class LinkLessonOut(Schema):
    code: str
    title: str
    total: int
    pending: int


class LinkExampleOut(Schema):
    number: int
    page: int | None
    skill: str


class LinkExerciseOut(Schema):
    kind: str
    number: int
    page: int | None
    examples: list[int]
    provenance: str
    reviewed: bool


class LessonLinksOut(Schema):
    examples: list[LinkExampleOut]
    exercises: list[LinkExerciseOut]


class ReviewIn(Schema):
    examples: list[int] = Field(min_length=1, max_length=20)


def _require_superuser(request: HttpRequest) -> None:
    if not request.user.is_superuser:
        raise HttpError(403, "للمشرف العام فقط")


def _links(course: str, lesson: str) -> dict:
    found = selectors.lesson_links(course, lesson)
    if found is None:
        raise HttpError(404, "لا تمارين مربوطة لهذا الدرس")
    return found


@router.get("/exercise-links/{course}", response=list[LinkLessonOut])
def link_lessons(request: HttpRequest, course: str):
    _require_superuser(request)
    return selectors.link_lessons(course)


@router.get("/exercise-links/{course}/{lesson}", response=LessonLinksOut)
def lesson_links(request: HttpRequest, course: str, lesson: str):
    _require_superuser(request)
    return _links(course, lesson)


@router.put("/exercise-links/{course}/{lesson}/{kind}/{number}", response=LessonLinksOut)
def review_link(
    request: HttpRequest,
    course: str,
    lesson: str,
    kind: Literal["try", "practice"],
    number: int,
    payload: ReviewIn,
):
    _require_superuser(request)
    try:
        services.review_exercise_link(
            course=course,
            lesson=lesson,
            kind=kind,
            number=number,
            examples=payload.examples,
            user=request.user,
            request_id=request_id_of(request),
        )
    except services.LinkNotFoundError as error:
        raise HttpError(404, str(error)) from error
    except services.LinkError as error:
        raise HttpError(422, str(error)) from error
    return _links(course, lesson)


@router.post("/exercise-links/{course}/{lesson}/approve", response=LessonLinksOut)
def approve_lesson(request: HttpRequest, course: str, lesson: str):
    _require_superuser(request)
    services.approve_lesson_links(
        course=course, lesson=lesson, user=request.user, request_id=request_id_of(request)
    )
    return _links(course, lesson)
