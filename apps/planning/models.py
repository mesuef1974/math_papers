"""نماذج نحيلة: نتيجة الصف في الدرس وتقرير الحصة (مستوى الشعبة فقط، لا بيانات طلاب فردية: PDPPL)، ومراجعة المعلم لأهداف حصته.

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


# ───── مراجعة المعلم لأهداف حصته (docs/teacher_objective_review_plan.md) ─────


class ObjectiveOverride(TimeStampedModel):
    """نسخة المعلم الشخصية لشرط هدف مثال ومعياره؛ السلوك وفعله وعمقه من ملف الوحدة المعتمد."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="objective_overrides"
    )
    lesson = models.ForeignKey(
        "curriculum.Lesson", on_delete=models.PROTECT, related_name="objective_overrides"
    )
    example = models.PositiveSmallIntegerField()
    condition = models.CharField(max_length=240)
    criterion = models.CharField(max_length=240)
    base_digest = models.CharField(max_length=16)  # بصمة النص المعتمد حين عُدِّل: تغيّرها يجعل النسخة قديمة

    class Meta:
        ordering = ["lesson_id", "example"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "lesson", "example"], name="planning_override_one_per_example"
            ),
            models.CheckConstraint(condition=Q(example__gte=1), name="planning_override_example_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.owner_id} · {self.lesson.code} مثال {self.example}"


class ObjectiveSuggestion(TimeStampedModel):
    """لقطة ثابتة من تعديل معلم يقترحه للنسخة المعتمدة، وقرار المالك فيها. «مُطبَّق» مشتق من ملف الوحدة."""

    PENDING, ACCEPTED, REJECTED = "pending", "accepted", "rejected"
    DECISIONS = [(PENDING, "قيد المراجعة"), (ACCEPTED, "مقبول"), (REJECTED, "مرفوض")]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="objective_suggestions"
    )
    lesson = models.ForeignKey(
        "curriculum.Lesson", on_delete=models.PROTECT, related_name="objective_suggestions"
    )
    example = models.PositiveSmallIntegerField()
    condition = models.CharField(max_length=240)
    criterion = models.CharField(max_length=240)
    base_digest = models.CharField(max_length=16)
    note = models.CharField(max_length=240, blank=True, default="")
    decision = models.CharField(max_length=8, choices=DECISIONS, default=PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=240, blank=True, default="")

    class Meta:
        ordering = ["-created_at", "-id"]
        permissions = [("decide_objective_suggestion", "يقبل اقتراحات المعلمين لنصوص الأهداف أو يرفضها")]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "lesson", "example"],
                condition=Q(decision="pending"),
                name="planning_suggestion_one_pending_per_example",
            ),
            models.CheckConstraint(
                condition=Q(decision__in=["pending", "accepted", "rejected"]),
                name="planning_suggestion_decision_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.lesson.code} مثال {self.example}: {self.get_decision_display()}"


class PrepReview(TimeStampedModel):
    """علامة «راجعتُ أهداف الحصة» بتاريخها وبصمة النصوص التي رآها المعلم؛ تغيّرها يجعل العلامة تحتاج مراجعة."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="prep_reviews")
    lesson = models.ForeignKey("curriculum.Lesson", on_delete=models.PROTECT, related_name="prep_reviews")
    k = models.PositiveSmallIntegerField()
    digest = models.CharField(max_length=16)
    reviewed_at = models.DateTimeField()

    class Meta:
        ordering = ["-reviewed_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "lesson", "k"], name="planning_review_one_per_period"),
            models.CheckConstraint(condition=Q(k__gte=1), name="planning_review_period_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.owner_id} · {self.lesson.code} الحصة {self.k}"
