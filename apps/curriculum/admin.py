from django.contrib import admin

from .models import (
    AcademicCalendar,
    Blueprint,
    BlueprintItem,
    CalendarEvent,
    CalendarTerm,
    Course,
    Lesson,
    PastExam,
    PastExamItem,
    PlanEnrichment,
    PlanWeek,
    ResourceCoverage,
    SourceDocument,
    TermPlan,
)

# الجداول كلها يملؤها المحمِّل الواحد من العقد القانوني: اللوحة للعرض والتحقق، والتعديل فيها يمحوه التحميل التالي.


class BlueprintItemInline(admin.TabularInline):
    model = BlueprintItem
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "grade", "track", "semester", "academic_year", "language", "is_current")
    list_filter = ("academic_year", "grade", "semester", "language")
    search_fields = ("slug", "title")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "course", "unit", "examinable")
    list_filter = ("course", "examinable")
    list_select_related = ("course",)
    search_fields = ("code", "title")


@admin.register(Blueprint)
class BlueprintAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "academic_year",
        "semester",
        "assessment",
        "scope",
        "total_marks",
        "is_forecast",
    )
    list_filter = ("course", "assessment", "scope", "is_forecast")
    list_select_related = ("course",)
    inlines = [BlueprintItemInline]


@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = ("slug", "kind", "course", "academic_year", "pages")
    list_filter = ("kind", "course", "academic_year")
    list_select_related = ("course",)
    search_fields = ("slug", "title", "sha256")


class PastExamItemInline(admin.TabularInline):
    model = PastExamItem
    extra = 0


@admin.register(PastExam)
class PastExamAdmin(admin.ModelAdmin):
    list_display = ("slug", "course", "academic_year", "semester", "assessment", "attempt", "total_marks")
    list_filter = ("course", "assessment", "attempt")
    list_select_related = ("course",)
    inlines = [PastExamItemInline]


@admin.register(ResourceCoverage)
class ResourceCoverageAdmin(admin.ModelAdmin):
    list_display = ("source", "lesson", "items", "solved", "mcq", "essay")
    list_select_related = ("source", "lesson")


class CalendarTermInline(admin.TabularInline):
    model = CalendarTerm
    extra = 0


@admin.register(AcademicCalendar)
class AcademicCalendarAdmin(admin.ModelAdmin):
    list_display = ("year", "verified_primary")
    inlines = [CalendarTermInline]


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ("term", "kind", "start", "end", "label")
    list_filter = ("kind",)


class PlanWeekInline(admin.TabularInline):
    model = PlanWeek
    extra = 0


class PlanEnrichmentInline(admin.TabularInline):
    model = PlanEnrichment
    extra = 0


@admin.register(TermPlan)
class TermPlanAdmin(admin.ModelAdmin):
    list_display = ("course", "sessions_per_week", "source")
    list_select_related = ("course", "source")
    inlines = [PlanWeekInline, PlanEnrichmentInline]
