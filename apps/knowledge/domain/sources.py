"""مخططات المصادر في العقد القانوني: الملفات المصدرية، والخطة الفصلية، والاختبارات السابقة، وتغطية المذكرات، والتقويم.

أعداد وتواريخ وفئات مغلقة فقط: لا حقل نص حر يحمل محتوى وثيقة. العناوين والملاحظات بصياغتنا. التحقق الدلالي للخطة
الفصلية (أسبوع من الأحد إلى الخميس ومجموع حصصه وما يتصل به) يعيد استعمال محرك التخطيط نفسه فلا يتكرر.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .schemas import LESSON_CODE

YEAR = r"^\d{4}-\d{4}$"
SLUG = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
SOURCE_KINDS = (
    "teacher_guide",
    "student_book",
    "term_plan",
    "blueprint",
    "past_exam",
    "notes",
    "solutions",
)
ASSESSMENTS = ("midterm", "final")
# جدول المواصفات قد يكون لاختبار الملحق (إعادة نهاية الفصل)؛ الخطة الفصلية لا تجدوله
BLUEPRINT_ASSESSMENTS = (*ASSESSMENTS, "makeup")
SCOPES = ("full", "first_half", "second_half")
PLAN_ITEM_KINDS = ("lesson", "review", "quiz", "orientation", "exam", "project", "support")
CLOSURE_KINDS = ("exam", "break", "holiday", "other")
WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceData(Strict):
    """ملف مصدر خارج المستودع: هويته وتجزئته فقط.

    التجزئة خلاصة بصيغة `sha256:<hex>`: البادئة تسمّي الخوارزمية وتمنع كاشف الأسرار من عدّ التجزئة سرًّا.
    """

    slug: str = Field(pattern=SLUG, max_length=64)
    kind: Literal[*SOURCE_KINDS]  # type: ignore[valid-type]
    title: str = Field(min_length=1, max_length=160)
    academic_year: str = Field(pattern=YEAR)
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    pages: int | None = Field(default=None, ge=1, le=2000)
    note: str = ""

    @property
    def sha256(self) -> str:
        return self.digest.removeprefix("sha256:")


class SlotData(Strict):
    """خانة في جدول مواصفات أو اختبار سابق: فرع من سؤال يقيس درسًا بنوع ودرجة ومستوى."""

    question_number: int = Field(ge=1, le=99)
    position: int = Field(default=1, ge=1, le=9)
    lesson: str = Field(pattern=LESSON_CODE)
    kind: Literal["mcq", "essay"]
    marks: int = Field(ge=1, le=50)
    level: Literal["K", "A", "R"] | None = None  # None = أي مستوى
    needs_graph: bool = False


class BlueprintSlotData(SlotData):
    """خانة جدول مواصفات: ومعها مجموعة دروس الوزارة التي تملكها (فارغ = بلا تدوير في النموذج ب)."""

    group: str = Field(default="", max_length=16, pattern=r"^[a-z0-9]*$")


def repeated_slots(items: list[SlotData]) -> list[tuple[int, int]]:
    slots = [(item.question_number, item.position) for item in items]
    return sorted({slot for slot in slots if slots.count(slot) > 1})


class PastExamItemData(SlotData):
    dok: int | None = Field(default=None, ge=1, le=4)


class PastExamData(Strict):
    """اختبار سابق مسقَطًا على دروس المقرر. مجموع درجات البنود وما لم يُسقَط يساوي الدرجة الكلية."""

    slug: str = Field(pattern=SLUG, max_length=64)
    source: str | None = None
    academic_year: str = Field(pattern=YEAR)
    semester: int = Field(ge=1, le=3)
    assessment: Literal[*ASSESSMENTS]  # type: ignore[valid-type]
    scope: Literal[*SCOPES] = "full"  # type: ignore[valid-type]
    attempt: Literal["main", "makeup"] = "main"
    total_marks: int = Field(ge=1, le=200)
    unmapped_marks: int = Field(default=0, ge=0)
    items: list[PastExamItemData] = Field(min_length=1)

    def model_post_init(self, __context: object) -> None:
        repeated = repeated_slots(self.items)
        if repeated:
            raise ValueError(f"خانة مكررة في الاختبار السابق {self.slug}: {repeated}")
        total = sum(item.marks for item in self.items) + self.unmapped_marks
        if total != self.total_marks:
            raise ValueError(f"درجات الاختبار السابق {self.slug} مجموعها {total} والمعلن {self.total_marks}")


class CoverageRowData(Strict):
    lesson: str = Field(pattern=LESSON_CODE)
    items: int = Field(ge=1, le=999)
    solved: int = Field(default=0, ge=0)
    mcq: int = Field(default=0, ge=0)
    essay: int = Field(default=0, ge=0)

    def model_post_init(self, __context: object) -> None:
        if self.solved > self.items or self.mcq + self.essay > self.items:
            raise ValueError(f"تغطية الدرس {self.lesson}: المحلول أو الأنواع أكثر من البنود")


class CoverageData(Strict):
    """ما تغطيه مذكرة أو ملف حلول، درسًا درسًا."""

    source: str
    lessons: list[CoverageRowData] = Field(min_length=1)

    def model_post_init(self, __context: object) -> None:
        codes = [row.lesson for row in self.lessons]
        if len(codes) != len(set(codes)):
            raise ValueError(f"درس مكرر في تغطية {self.source}")


class PlanItemData(Strict):
    kind: Literal[*PLAN_ITEM_KINDS]  # type: ignore[valid-type]
    periods: int = Field(ge=1, le=10)
    lesson: str | None = Field(default=None, pattern=LESSON_CODE)
    unit: int | None = Field(default=None, ge=1, le=30)
    scope: Literal[*ASSESSMENTS] | None = None  # type: ignore[valid-type]


class PlanWeekData(Strict):
    n: int = Field(ge=1, le=30)
    start: date
    end: date
    items: list[PlanItemData] = Field(min_length=1)


class ExamWindowData(Strict):
    start: date
    end: date
    note: str = ""


class TermPlanData(Strict):
    """الخطة الفصلية لمقرر (الفصل والسنة من المقرر): الأسابيع وبنودها بحصصها، والأيام الفاقدة، والإثرائي."""

    source: str | None = None
    sessions_per_week: int = Field(default=5, ge=1, le=10)
    class_during_exams: ExamWindowData | None = None
    lost_days: list[date] = Field(default_factory=list)
    enrichment_lessons: list[str] = Field(default_factory=list)
    enrichment_examples: dict[str, list[int]] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    weeks: list[PlanWeekData] = Field(min_length=1)

    def to_domain(self, semester: int):
        """الخطة كما يقرؤها محرك التخطيط، بعد تحققه الكامل منها (يرفع `PlanningError`)."""
        from apps.planning.domain.semester_plan import parse_term_plan

        return parse_term_plan(self.model_dump(mode="json"), semester)


class ClosureData(Strict):
    start: date
    end: date
    kind: Literal[*CLOSURE_KINDS]  # type: ignore[valid-type]
    label: str = Field(default="", max_length=120)
    grades: list[int] = Field(default_factory=list)  # فارغة = كل الصفوف


class CalendarTermData(Strict):
    semester: int = Field(ge=1, le=3)
    start: date
    end: date
    closures: list[ClosureData] = Field(default_factory=list)

    def model_post_init(self, __context: object) -> None:
        if self.end < self.start:
            raise ValueError(f"الفصل {self.semester} ينتهي قبل أن يبدأ")
        for closure in self.closures:
            if closure.end < closure.start or closure.start < self.start or closure.end > self.end:
                raise ValueError(f"إغلاق خارج حدّ الفصل {self.semester} أو مقلوب: {closure.start}")


class CalendarData(Strict):
    """تقويم سنة أكاديمية: ملف لكل سنة في `apps/knowledge/data/calendars/<السنة>.json`."""

    year: str = Field(pattern=YEAR)
    grades: list[int] = Field(default_factory=list)
    source: str = ""
    verified_primary: bool = False
    weekdays: list[Literal[*WEEKDAY_NAMES]] = Field(min_length=1)  # type: ignore[valid-type]
    unknown: list[str] = Field(default_factory=list)
    terms: list[CalendarTermData] = Field(min_length=1)

    def model_post_init(self, __context: object) -> None:
        semesters = [term.semester for term in self.terms]
        if len(semesters) != len(set(semesters)):
            raise ValueError(f"فصل مكرر في تقويم {self.year}")
