"""مسارات التوليد. قراءة فقط: GET يعطي الورقة نفسها لكل بذرة، وكلها للمعلمين المسجّلين، بمعدل محدود لكل مستخدم."""

from typing import Annotated, Literal

from django.http import HttpRequest
from ninja import Field, Query, Router, Schema
from ninja.errors import HttpError
from ninja.throttling import UserRateThrottle

from apps.curriculum import selectors

from . import selectors as paper_selectors
from . import services
from .access import TeacherAuth
from .domain.generators import ExhaustedError, available_lessons, lesson_levels

router = Router(tags=["الأوراق"], auth=TeacherAuth(), throttle=[UserRateThrottle()])
Seed = Annotated[int, Field(ge=0, le=services.MAX_SEED)]


class LessonOut(Schema):
    code: str
    title: str
    unit: int
    examinable: bool
    has_generator: bool
    levels: list[str]


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


class SlotOut(Schema):
    """قيود الخانة كما وُلِّدت، لإعادة التوليد أو الاستبدال بالقيود نفسها."""

    kind: str
    level: str
    needs_graph: bool


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
    option_graphs: list[GraphOut] = []
    variant: str
    fingerprint: str
    slot: SlotOut


class QuestionOut(Schema):
    number: int
    kind: str
    marks: int
    parts: list[PartOut]


class PaperOut(Schema):
    kind: Literal["exam", "worksheet"]
    generator_version: str
    blueprint: str
    lesson_code: str
    title: str
    seed: int
    total_marks: int
    is_forecast: bool
    level_marks: dict[str, int]
    questions: list[QuestionOut]
    level: str = ""


class ExamQuery(Schema):
    blueprint: str
    seed: Seed | None = None


class WorksheetQuery(Schema):
    lesson: str
    count: Annotated[int, Field(ge=1, le=20)] = 8
    seed: Seed | None = None
    level: Literal["K", "A", "R"] | None = None


class PrintProfileOut(Schema):
    school: str
    teacher_name: str
    subject: str
    grade: str
    exam_minutes: int
    exam_instructions: str
    worksheet_instructions: str


class PrintProfileIn(Schema):
    school: str = Field("", max_length=160)
    teacher_name: str = Field("", max_length=120)
    subject: str = Field(min_length=1, max_length=80)
    grade: str = Field("", max_length=120)
    exam_minutes: int = Field(ge=10, le=300)
    exam_instructions: str = Field("", max_length=500)
    worksheet_instructions: str = Field("", max_length=500)


EXHAUSTED = "تعذر توليد مسائل مختلفة بهذا العدد. غيّر رقم النموذج أو قلّل العدد."


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
            "levels": lesson_levels(row.code) if row.code in ready else [],
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
    except ExhaustedError as error:
        raise HttpError(409, EXHAUSTED) from error


@router.get("/papers/worksheet", response=PaperOut)
def worksheet(request: HttpRequest, query: Query[WorksheetQuery]):
    try:
        return services.build_worksheet(query.lesson, query.count, query.seed, query.level)
    except services.UnknownLessonError as error:
        raise HttpError(404, "الدرس غير متاح بهذا المستوى") from error
    except ExhaustedError as error:
        raise HttpError(409, EXHAUSTED) from error


@router.get("/print-profile", response=PrintProfileOut)
def get_print_profile(request: HttpRequest):
    return paper_selectors.print_profile(request.user)


@router.put("/print-profile", response=PrintProfileOut)
def put_print_profile(request: HttpRequest, payload: PrintProfileIn):
    cleaned = {
        key: value.strip() if isinstance(value, str) else value for key, value in payload.dict().items()
    }
    return services.save_print_profile(request.user, cleaned)
