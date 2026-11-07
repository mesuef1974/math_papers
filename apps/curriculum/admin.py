from django.contrib import admin

from .models import Blueprint, BlueprintItem, Lesson


class BlueprintItemInline(admin.TabularInline):
    model = BlueprintItem
    extra = 0


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "unit", "examinable")


@admin.register(Blueprint)
class BlueprintAdmin(admin.ModelAdmin):
    list_display = ("title", "academic_year", "semester", "total_marks", "is_forecast")
    inlines = [BlueprintItemInline]
