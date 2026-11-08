from django.contrib import admin

from .models import PrintProfile


@admin.register(PrintProfile)
class PrintProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "teacher_name", "exam_minutes", "updated_at")
    search_fields = ("user__username", "school", "teacher_name")
