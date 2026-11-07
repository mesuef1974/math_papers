from django.contrib import admin

from .models import (
    ExerciseTemplate,
    LessonItem,
    LessonProfile,
    PedagogyNote,
    Standard,
    Term,
    UnitProfile,
    UnitProject,
    WorkedExample,
)


class LessonItemInline(admin.TabularInline):
    model = LessonItem
    extra = 0


class ExerciseTemplateInline(admin.TabularInline):
    model = ExerciseTemplate
    extra = 0


@admin.register(LessonProfile)
class LessonProfileAdmin(admin.ModelAdmin):
    list_display = ("lesson", "objective")
    inlines = [LessonItemInline, ExerciseTemplateInline]


admin.site.register([Standard, Term, WorkedExample, UnitProfile, UnitProject, PedagogyNote])
