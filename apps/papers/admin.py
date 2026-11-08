from django.contrib import admin

from .models import PrintProfile, SavedPaper


@admin.register(PrintProfile)
class PrintProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "teacher_name", "exam_minutes", "updated_at")
    search_fields = ("user__username", "school", "teacher_name")


@admin.register(SavedPaper)
class SavedPaperAdmin(admin.ModelAdmin):
    """قراءة فقط من الإدارة: الورقة ملك معلمها ويعدّلها من الواجهة، والحذف من هنا للدعم فقط."""

    list_display = (
        "title",
        "owner",
        "kind",
        "lesson_code",
        "seed",
        "question_count",
        "replacement_count",
        "updated_at",
    )
    list_filter = ("kind",)
    search_fields = ("title", "owner__username", "lesson_code", "blueprint")
    readonly_fields = tuple(f.name for f in SavedPaper._meta.fields)
    exclude = ("snapshot", "recipe")

    def has_add_permission(self, request):
        return False
