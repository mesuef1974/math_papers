"""تحضير الوحدة: أهداف أمثلتها بصيغة ABCD بصياغتنا وحالة اعتمادها، من `prep/unit-<n>.json` في مجلد المقرر.

يكتبها المحمِّل الواحد (`services.sync_prep_unit`) ويقرؤها اشتقاق تحضير الحصة (`apps.planning.selectors.lesson_preps`).
الهدف لمثال لا لدرس، فهي خارج `knowledge.LessonObjective` (أهداف الدرس بمستويات بلوم من الفهرس المشتق، بلا نص).
"""

from __future__ import annotations

from django.db import models

from .catalog import Course, Lesson


class PrepUnit(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودة"
        APPROVED = "approved", "معتمدة"

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="prep_units")
    unit = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=8, choices=Status.choices)
    approval = models.CharField(max_length=200, blank=True)  # سطر اعتماد المالك وتاريخه
    audience = models.CharField(max_length=80)

    class Meta:
        ordering = ["course_id", "unit"]
        constraints = [models.UniqueConstraint(fields=["course", "unit"], name="unique_prep_unit")]

    def __str__(self) -> str:
        return f"{self.course_id} الوحدة {self.unit} ({self.status})"


class PrepObjective(models.Model):
    unit = models.ForeignKey(PrepUnit, on_delete=models.CASCADE, related_name="objectives")
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="+")
    example = models.PositiveSmallIntegerField()
    behavior = models.TextField()
    condition = models.TextField()
    criterion = models.TextField()

    class Meta:
        ordering = ["unit_id", "lesson_id", "example"]
        constraints = [models.UniqueConstraint(fields=["lesson", "example"], name="unique_prep_objective")]

    def __str__(self) -> str:
        return f"{self.lesson_id} مثال {self.example}"
