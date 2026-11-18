"""نماذج المنهج مقسّمة بالمجال: الكتالوج والمصادر والتقييم والزمن. حقول وقيود فقط، والكتابة في `services` والقراءة في
`selectors`."""

from .assessment import (
    Assessment,
    AssessmentSlot,
    Blueprint,
    BlueprintItem,
    PastExam,
    PastExamItem,
    Scope,
)
from .catalog import ACADEMIC_YEAR_LENGTH, Course, Lesson
from .schedule import (
    AcademicCalendar,
    CalendarEvent,
    CalendarTerm,
    PlanEnrichment,
    PlanEntry,
    PlanWeek,
    TermPlan,
)
from .sources import ResourceCoverage, SourceDocument

__all__ = [
    "ACADEMIC_YEAR_LENGTH",
    "AcademicCalendar",
    "Assessment",
    "AssessmentSlot",
    "Blueprint",
    "BlueprintItem",
    "CalendarEvent",
    "CalendarTerm",
    "Course",
    "Lesson",
    "PastExam",
    "PastExamItem",
    "PlanEnrichment",
    "PlanEntry",
    "PlanWeek",
    "ResourceCoverage",
    "Scope",
    "SourceDocument",
    "TermPlan",
]
