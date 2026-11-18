"""نموذجان نحيلان: نتيجة الصف في الدرس وتقرير الحصة. مستوى الشعبة فقط (لا بيانات طلاب فردية: PDPPL). المنطق في services.py.

السجل يرتبط بالدرس نفسه (`lesson`، ومنه مقرره): الرمز «1.1» درس مختلف في كل كتاب، ومعلم يدرّس صفّين لا تتصادم سجلاته.
`lesson` مطلوب وهو مصدر الرمز الوحيد (`lesson.code`): لا نسخة من الرمز في السجل.
"""

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
    lesson = models.ForeignKey("curriculum.Lesson", on_delete=models.PROTECT, related_name="class_outcomes")
    attempted = models.PositiveSmallIntegerField()
    correct = models.PositiveSmallIntegerField()
    pace = models.CharField(max_length=4, default="ok")
    obstacles = models.JSONField(default=list)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "section", "lesson"], name="planning_outcome_one_per_section_lesson_row"
            ),
            models.CheckConstraint(
                condition=Q(attempted__gte=1) & Q(correct__lte=F("attempted")),
                name="planning_outcome_counts_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.section} · {self.lesson.code}: {self.correct}/{self.attempted}"


class LessonRunRecord(TimeStampedModel):
    """تقرير حصة جرت: المخطط مقابل الفعلي لكل طور، كما سجّله وضع الحصة."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lesson_runs")
    section = models.CharField(max_length=20)
    lesson = models.ForeignKey("curriculum.Lesson", on_delete=models.PROTECT, related_name="lesson_runs")
    period_minutes = models.PositiveSmallIntegerField()
    started_at = models.DateTimeField()
    finished = models.BooleanField(default=False)
    phases = models.JSONField(default=list)

    class Meta:
        ordering = ["-started_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "section", "lesson", "started_at"], name="planning_run_one_per_lesson_start"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.section} · {self.lesson.code} @ {self.started_at:%Y-%m-%d %H:%M}"
