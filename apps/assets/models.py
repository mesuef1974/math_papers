"""فهرس الأصول: مقاطع الأمثلة من كتاب الطالب. الملفات في طبقة التخزين لا في القاعدة؛ هنا بياناتها وتجزئتها فقط."""

from __future__ import annotations

from django.db import models

from apps.curriculum.models import Course, Lesson


class Asset(models.Model):
    class Kind(models.TextChoices):
        EXAMPLE = "example", "مثال محلول"
        PRACTICE = "practice", "تدريب"

    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="assets")
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="assets")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    number = models.PositiveSmallIntegerField()  # رقم المثال أو التدريب في الدرس
    part = models.PositiveSmallIntegerField(default=0)  # 0 المقطع الأصلي، 1... تتمته إن امتد على صفحة تالية
    key = models.CharField(max_length=255, unique=True)  # مفتاح الملف في التخزين؛ يحمل جزءًا من التجزئة
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    width = models.PositiveSmallIntegerField()
    height = models.PositiveSmallIntegerField()
    content_type = models.CharField(max_length=40, default="image/png")
    # صفوف قص المقطع الطويل في شرائح العرض؛ NULL لم تُحسب أو لا فراغ آمن للقص، و[] لا يحتاج قصًّا
    cuts = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course_id", "lesson_id", "kind", "number", "part"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "lesson", "kind", "number", "part"], name="unique_asset_slot"
            )
        ]

    def __str__(self) -> str:
        return f"{self.course_id} {self.lesson_id} {self.kind} {self.number}.{self.part}"
