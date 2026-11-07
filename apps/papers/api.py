"""مسارات التوليد. قراءة فقط: GET يعطي الورقة نفسها لكل بذرة، وكلها للمعلمين المسجّلين."""

from typing import Annotated

from django.http import HttpRequest
from ninja import Field, Query, Router, Schema
from ninja.errors import HttpError

from apps.curriculum import selectors

from . import services
from .access import TeacherAuth
from .domain.generators import available_lessons

router = Router(tags=["الأوراق"], auth=TeacherAuth())
Seed = Annotated[int, Field(ge=0, le=services.MAX_SEED)]


class LessonOut(Schema):
    code: str
    title: str
    unit: int
    examinable: bool
    has_generator: bool


class BlueprintOut(Schema):
    slug: str
    title: str
    total_marks: int
    is_forecast: bool


class GraphOut(Schema):
    window: list[int]
    label: str
    curves: list[list[list[float]]]
    dots: list[tuple[float, float, bool]]
    asymptotes: list[float]
    lines: list[list[list[float]]]


class PartOut(Schema):
    label: str
    lesson: str
    lesson_title: str
    marks: int
    level: str
    stem: str
    options: list[str]
    answer: str
    steps: list[str]
    graph: GraphOut | None = None


class QuestionOut(Schema):
    number: int
    kind: str
    marks: int
    parts: list[PartOut]


class PaperOut(Schema):
    title: str
    seed: int
    total_marks: int
    is_forecast: bool
    level_marks: dict[str, int]
    questions: list[QuestionOut]


class ExamQuery(Schema):
    blueprint: str
    seed: Seed | None = None


class WorksheetQuery(Schema):
    lesson: str
    count: Annotated[int, Field(ge=1, le=20)] = 8
    seed: Seed | None = None


@router.get("/lessons", response=list[LessonOut])
def lessons(request: HttpRequest):
    ready = available_lessons()
    return [
        {
            "code": row.code,
            "title": row.title,
            "unit": row.unit,
            "examinable": row.examinable,
            "has_generator": row.code in ready,
        }
        for row in selectors.lessons()
    ]


@router.get("/blueprints", response=list[BlueprintOut])
def blueprints(request: HttpRequest):
    return list(selectors.blueprints())


@router.get("/papers/exam", response=PaperOut)
def exam(request: HttpRequest, query: Query[ExamQuery]):
    try:
        return services.build_exam(query.blueprint, query.seed)
    except services.UnknownBlueprintError as error:
        raise HttpError(404, "جدول المواصفات غير موجود") from error


@router.get("/papers/worksheet", response=PaperOut)
def worksheet(request: HttpRequest, query: Query[WorksheetQuery]):
    try:
        return services.build_worksheet(query.lesson, query.count, query.seed)
    except services.UnknownLessonError as error:
        raise HttpError(404, "الدرس غير متاح") from error
