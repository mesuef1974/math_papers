from django.contrib import admin

from .models import Blueprint, BlueprintItem, Course, Lesson


class BlueprintItemInline(admin.TabularInline):
    model = BlueprintItem
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "grade", "track", "semester", "language", "is_current")
    list_filter = ("grade", "semester", "language")
    search_fields = ("slug", "title")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "course", "unit", "examinable")
    list_filter = ("course", "examinable")
    list_select_related = ("course",)
    search_fields = ("code", "title")


@admin.register(Blueprint)
class BlueprintAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "academic_year", "semester", "total_marks", "is_forecast")
    list_filter = ("course",)
    list_select_related = ("course",)
    inlines = [BlueprintItemInline]
