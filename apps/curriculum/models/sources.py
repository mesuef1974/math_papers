"""المصادر: ملفات خارج المستودع (أدلة وخطط وجداول مواصفات واختبارات سابقة ومذكرات) بهويتها وتجزئتها لا بمحتواها.

كل صف مشتق من مصدر (خطة فصلية، جدول مواصفات، اختبار سابق، تغطية مذكرة) يشير إلى ملفه هنا، فيُعرف أصل كل رقم. نص
الملفات نفسها لا يدخل المستودع ولا الإنتاج.
"""

from __future__ import annotations

from django.db import models

from .catalog import ACADEMIC_YEAR_LENGTH, Course, Lesson


class SourceDocument(models.Model):
    class Kind(models.TextChoices):
        TEACHER_GUIDE = "teacher_guide", "دليل المعلم"
        STUDENT_BOOK = "student_book", "كتاب الطالب"
        TERM_PLAN = "term_plan", "الخطة الفصلية"
        BLUEPRINT = "blueprint", "جدول المواصفات"
        PAST_EXAM = "past_exam", "اختبار سابق"
        NOTES = "notes", "مذكرة"
        SOLUTIONS = "solutions", "حلول"

    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="sources")
    slug = models.SlugField(max_length=64)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    title = models.CharField(max_length=160)  # وصفنا للملف لا عنوانه المنسوخ
    # سنة الوثيقة نفسها (الاختبار السابق أقدم من المقرر)
    academic_year = models.CharField(max_length=ACADEMIC_YEAR_LENGTH)
    sha256 = models.CharField(max_length=64)
    pages = models.PositiveSmallIntegerField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["course_id", "kind", "-academic_year", "slug"]
        constraints = [
            models.UniqueConstraint(fields=["course", "slug"], name="unique_source_per_course"),
            # الملف الواحد مصدر واحد للمقرر: التجزئة تمنع تسجيله مرتين باسمين
            models.UniqueConstraint(fields=["course", "sha256"], name="unique_source_file_per_course"),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()}: {self.title}"


class ResourceCoverage(models.Model):
    """ما تغطيه مذكرة أو ملف حلول من درس: أعداد فقط (بنود ومحلول منها وموضوعي ومقالي)، بلا نص."""

    source = models.ForeignKey(SourceDocument, on_delete=models.CASCADE, related_name="coverage")
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="+")
    items = models.PositiveSmallIntegerField()
    solved = models.PositiveSmallIntegerField(default=0)
    mcq = models.PositiveSmallIntegerField(default=0)
    essay = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["source_id", "lesson_id"]
        constraints = [
            models.UniqueConstraint(fields=["source", "lesson"], name="unique_coverage_per_lesson"),
            models.CheckConstraint(
                condition=models.Q(solved__lte=models.F("items")), name="coverage_solved_le_items"
            ),
            models.CheckConstraint(
                condition=models.Q(mcq__lte=models.F("items") - models.F("essay")),
                name="coverage_kinds_le_items",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source_id} {self.lesson_id}: {self.items}"
