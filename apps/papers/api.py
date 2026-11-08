"""مسارات التوليد. قراءة فقط: GET يعطي الورقة نفسها لكل بذرة، وكلها للمعلمين المسجّلين، بمعدل محدود لكل مستخدم."""

from datetime import datetime
from typing import Annotated, Literal

from django.http import HttpRequest
from ninja import Field, Query, Router, Schema, Status
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
    answer_index: int = -1
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


Form = Literal["A", "B"]


Kind = Literal["exam", "worksheet", "quiz"]


class PaperOut(Schema):
    kind: Kind
    form: Form = "A"
    generator_version: str
    blueprint: str
    lesson_code: str
    title: str
    seed: int
    total_marks: int
    is_forecast: bool
    level_marks: dict[str, int]
    level_counts: dict[str, int] = {}  # لأوراق الحزمة: عدد المسائل لكل مستوى
    questions: list[QuestionOut]
    level: str = ""


class ExamQuery(Schema):
    blueprint: str
    seed: Seed | None = None
    form: Form = "A"


class WorksheetQuery(Schema):
    lesson: str
    count: Annotated[int, Field(ge=1, le=20)] = 8
    seed: Seed | None = None
    level: Literal["K", "A", "R"] | None = None
    form: Form = "A"
    purpose: Literal["", "remedial", "enrichment"] = ""


class QuizQuery(Schema):
    lessons: str = Field(min_length=3, max_length=12)  # «1.1» أو «1.1,1.2»
    seed: Seed | None = None
    form: Form = "A"


class BundleEntryOut(Schema):
    lesson: str
    title: str
    count: int
    levels: dict[str, int]


class BundleQuery(Schema):
    blueprint: str


class BundleItemQuery(Schema):
    blueprint: str
    lesson: str
    seed: Seed


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


class ReplacePartIn(Schema):
    """طلب بديل لجزء: الخانة كما حُفظت مع الجزء، وبصمات ما في الورقة حتى لا يتكرر."""

    lesson: str = Field(max_length=10)
    label: str = Field("", max_length=1)
    marks: int = Field(0, ge=0, le=20)
    slot: SlotOut
    exclude: list[Annotated[str, Field(max_length=12)]] = Field([], max_length=200)
    seed: Seed | None = None


class ReplacedPartOut(PartOut):
    seed: int  # بذرة الاستبدال، تُدوَّن في الوصفة ليُعاد البناء


class ReplacementIn(Schema):
    question: int = Field(ge=1, le=60)
    label: str = Field("", max_length=1)
    seed: Seed
    fingerprint: str = Field(max_length=12)


class RecipeIn(Schema):
    """كيف وُلّدت الورقة: المعاملات ثم الاستبدالات بترتيبها. هوية الورقة المحفوظة."""

    kind: Kind
    form: Form = "A"
    blueprint: str = Field("", max_length=80)
    lesson_code: str = Field("", max_length=12)
    count: int = Field(0, ge=0, le=20)
    level: Literal["K", "A", "R", ""] = ""
    purpose: Literal["", "remedial", "enrichment"] = ""
    seed: Seed
    replacements: list[ReplacementIn] = Field([], max_length=60)


class SavePaperIn(Schema):
    title: str = Field("", max_length=200)
    paper: PaperOut
    recipe: RecipeIn


class SavedPatchIn(Schema):
    title: str | None = Field(None, max_length=200)
    paper: PaperOut | None = None
    recipe: RecipeIn | None = None


class SavedSummaryOut(Schema):
    id: int
    title: str
    kind: str
    blueprint: str
    lesson_code: str
    seed: int
    total_marks: int
    question_count: int
    replacement_count: int
    generator_version: str
    created_at: datetime
    updated_at: datetime


class SavedPaperOut(SavedSummaryOut):
    paper: PaperOut = Field(alias="snapshot")
    recipe: RecipeIn


EXHAUSTED = "تعذر توليد مسائل مختلفة بهذا العدد. غيّر رقم النموذج أو قلّل العدد."
REPLACE_EXHAUSTED = "تعذر إيجاد مسألة مختلفة لهذه الخانة. جرّب مرة أخرى."
SAVED_LIMIT = f"بلغت الحد الأقصى ({services.MAX_SAVED_PER_USER} ورقة). احذف بعض الأوراق القديمة."
SAVED_CONFLICT = "هذا التعديل يجعل الورقة نسخة من ورقة محفوظة أخرى."
KIND_MISMATCH = "نوع الورقة في الوصفة لا يطابق اللقطة."


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
        return services.build_exam(query.blueprint, query.seed, query.form)
    except services.UnknownBlueprintError as error:
        raise HttpError(404, "جدول المواصفات غير موجود") from error
    except ExhaustedError as error:
        raise HttpError(409, EXHAUSTED) from error


@router.get("/papers/worksheet", response=PaperOut)
def worksheet(request: HttpRequest, query: Query[WorksheetQuery]):
    try:
        return services.build_worksheet(
            query.lesson, query.count, query.seed, query.level, query.form, query.purpose
        )
    except services.UnknownLessonError as error:
        raise HttpError(404, "الدرس غير متاح بهذا المستوى") from error
    except ExhaustedError as error:
        raise HttpError(409, EXHAUSTED) from error


@router.get("/papers/quiz", response=PaperOut)
def quiz(request: HttpRequest, query: Query[QuizQuery]):
    codes = [code.strip() for code in query.lessons.split(",") if code.strip()]
    if not 1 <= len(codes) <= services.QUIZ_MAX_LESSONS:
        raise HttpError(422, "الاختبار القصير لدرس واحد أو درسين.")
    try:
        return services.build_quiz(codes, query.seed, query.form)
    except services.UnknownLessonError as error:
        raise HttpError(404, "درس غير متاح") from error
    except ExhaustedError as error:
        raise HttpError(409, EXHAUSTED) from error


@router.get("/papers/bundle-plan", response=list[BundleEntryOut])
def bundle_plan(request: HttpRequest, query: Query[BundleQuery]):
    """خطة حزمة كل أوراق العمل من جدول المواصفات؛ الواجهة تطلب أوراقها بالتوازي من bundle-item."""
    try:
        return services.bundle_plan(query.blueprint)
    except services.UnknownBlueprintError as error:
        raise HttpError(404, "جدول المواصفات غير موجود") from error


@router.get("/papers/bundle-item", response=PaperOut)
def bundle_item(request: HttpRequest, query: Query[BundleItemQuery]):
    try:
        return services.build_bundle_item(query.blueprint, query.lesson, query.seed)
    except services.UnknownBlueprintError as error:
        raise HttpError(404, "جدول المواصفات غير موجود") from error
    except services.UnknownLessonError as error:
        raise HttpError(404, "الدرس ليس في الحزمة") from error
    except ExhaustedError as error:
        raise HttpError(409, EXHAUSTED) from error


@router.post("/papers/replace-part", response=ReplacedPartOut)
def replace_part(request: HttpRequest, payload: ReplacePartIn):
    slot = services.PartSlot(
        payload.label,
        payload.lesson,
        "",
        payload.slot.kind,
        payload.marks,
        payload.slot.level,
        payload.slot.needs_graph,
    )
    try:
        return services.replacement_part(payload.lesson, slot, set(payload.exclude), payload.seed)
    except services.UnknownLessonError as error:
        raise HttpError(404, "الدرس غير متاح") from error
    except ExhaustedError as error:
        raise HttpError(409, REPLACE_EXHAUSTED) from error


def _recipe_dict(recipe: RecipeIn) -> dict:
    return recipe.dict()


@router.get("/saved", response=list[SavedSummaryOut])
def saved_list(request: HttpRequest):
    return list(paper_selectors.saved_papers(request.user))


@router.post("/saved", response={200: SavedPaperOut, 201: SavedPaperOut})
def saved_create(request: HttpRequest, payload: SavePaperIn):
    """201 عند الحفظ، و200 إن كانت الوصفة نفسها محفوظة من قبل (idempotent)."""
    if payload.paper.kind != payload.recipe.kind:
        raise HttpError(422, KIND_MISMATCH)
    try:
        row, created = services.save_paper(
            request.user, payload.title.strip(), payload.paper.dict(), _recipe_dict(payload.recipe)
        )
    except services.SavedLimitError as error:
        raise HttpError(409, SAVED_LIMIT) from error
    return Status(201 if created else 200, row)


@router.get("/saved/{int:pk}", response=SavedPaperOut)
def saved_detail(request: HttpRequest, pk: int):
    row = paper_selectors.saved_paper(request.user, pk)
    if row is None:
        raise HttpError(404, "الورقة غير موجودة")
    return row


@router.patch("/saved/{int:pk}", response=SavedPaperOut)
def saved_update(request: HttpRequest, pk: int, payload: SavedPatchIn):
    if (payload.paper is None) != (payload.recipe is None):
        raise HttpError(422, "اللقطة والوصفة تُحدَّثان معًا.")
    if payload.paper is not None and payload.recipe is not None and payload.paper.kind != payload.recipe.kind:
        raise HttpError(422, KIND_MISMATCH)
    try:
        row = services.update_saved_paper(
            request.user,
            pk,
            title=payload.title,
            snapshot=payload.paper.dict() if payload.paper is not None else None,
            recipe=_recipe_dict(payload.recipe) if payload.recipe is not None else None,
        )
    except services.SavedConflictError as error:
        raise HttpError(409, SAVED_CONFLICT) from error
    if row is None:
        raise HttpError(404, "الورقة غير موجودة")
    return row


@router.delete("/saved/{int:pk}", response={204: None})
def saved_delete(request: HttpRequest, pk: int):
    services.delete_saved_paper(request.user, pk)
    return Status(204, None)


@router.get("/print-profile", response=PrintProfileOut)
def get_print_profile(request: HttpRequest):
    return paper_selectors.print_profile(request.user)


@router.put("/print-profile", response=PrintProfileOut)
def put_print_profile(request: HttpRequest, payload: PrintProfileIn):
    cleaned = {
        key: value.strip() if isinstance(value, str) else value for key, value in payload.dict().items()
    }
    return services.save_print_profile(request.user, cleaned)
