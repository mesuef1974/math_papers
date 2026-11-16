"""نموذجان نحيلان: نتيجة الصف في الدرس وتقرير الحصة. مستوى الشعبة فقط (لا بيانات طلاب فردية: PDPPL). المنطق في services.py."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel


class ClassOutcomeRecord(TimeStampedModel):
    """آخر نتيجة بطاقة خروج لشعبة في درس: أعداد ونبض وعوائق بفئات مغلقة. القرار يُشتق منها ولا يُخزَّن."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="class_outcomes"
    )
    section = models.CharField(max_length=20)
    lesson_code = models.CharField(max_length=10)
    attempted = models.PositiveSmallIntegerField()
    correct = models.PositiveSmallIntegerField()
    pace = models.CharField(max_length=4, default="ok")
    obstacles = models.JSONField(default=list)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "section", "lesson_code"], name="planning_outcome_one_per_section_lesson"
            ),
            models.CheckConstraint(
                condition=Q(attempted__gte=1) & Q(correct__lte=F("attempted")),
                name="planning_outcome_counts_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.section} · {self.lesson_code}: {self.correct}/{self.attempted}"


class LessonRunRecord(TimeStampedModel):
    """تقرير حصة جرت: المخطط مقابل الفعلي لكل طور، كما سجّله وضع الحصة."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lesson_runs")
    section = models.CharField(max_length=20)
    lesson_code = models.CharField(max_length=10)
    period_minutes = models.PositiveSmallIntegerField()
    started_at = models.DateTimeField()
    finished = models.BooleanField(default=False)
    phases = models.JSONField(default=list)

    class Meta:
        ordering = ["-started_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "section", "lesson_code", "started_at"], name="planning_run_one_per_start"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.section} · {self.lesson_code} @ {self.started_at:%Y-%m-%d %H:%M}"
