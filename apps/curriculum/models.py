"""نماذج المنهج: الدروس وجداول المواصفات. حقول وقيود فقط."""

from __future__ import annotations

from django.db import models


class Lesson(models.Model):
    code = models.CharField(max_length=8, unique=True)
    title = models.CharField(max_length=120)
    unit = models.PositiveSmallIntegerField()
    examinable = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} {self.title}"


class Blueprint(models.Model):
    """جدول مواصفات. is_forecast يعني أنه توقع غير رسمي، فالوزارة لا تصدر جداول للثانوية العامة."""

    slug = models.SlugField(max_length=64, unique=True)
    title = models.CharField(max_length=160)
    academic_year = models.CharField(max_length=9)
    semester = models.PositiveSmallIntegerField()
    total_marks = models.PositiveSmallIntegerField()
    is_forecast = models.BooleanField(default=True)

    class Meta:
        ordering = ["-academic_year", "semester"]
        permissions = [("generate_paper", "يولّد اختبارات وأوراق عمل")]

    def __str__(self) -> str:
        return self.title


class BlueprintItem(models.Model):
    class Kind(models.TextChoices):
        MCQ = "mcq", "موضوعي"
        ESSAY = "essay", "مقالي"

    class Level(models.TextChoices):
        EASY = "K", "سهل"
        MEDIUM = "A", "متوسط"
        HIGHER = "R", "مهارات عليا"

    blueprint = models.ForeignKey(Blueprint, on_delete=models.CASCADE, related_name="items")
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="+")
    question_number = models.PositiveSmallIntegerField()
    position = models.PositiveSmallIntegerField(default=1)
    kind = models.CharField(max_length=5, choices=Kind.choices)
    marks = models.PositiveSmallIntegerField()
    # فارغ = أي مستوى. التوسعة nullable حتى تعمل النسخة السابقة أثناء النشر.
    level = models.CharField(max_length=1, choices=Level.choices, null=True, blank=True)
    needs_graph = models.BooleanField(default=False, db_default=False)

    class Meta:
        ordering = ["question_number", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["blueprint", "question_number", "position"], name="unique_blueprint_slot"
            )
        ]

    def __str__(self) -> str:
        return f"{self.question_number}.{self.position} {self.lesson_id}"
