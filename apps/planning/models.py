"""نماذج نحيلة: نتيجة الصف في الدرس وتقرير الحصة (مستوى الشعبة)، ومراجعة المعلم لأهداف حصته، ونتيجة الطالب لكل بند.

بيانات الطالب الفردية (PDPPL، قرار المالك 2026-11-25) في `SectionStudent` و`ItemResult` وحدهما: رقم قيد واسم مختصر، تُحذف
بنهاية السنة الأكاديمية (`services.purge_ended_results`)، ولا تدخل أسماؤها سجل التدقيق.

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


class PeriodPrepOverride(TimeStampedModel):
    """تعديل المعلم لتحضير حصص درس، له وحده (`domain/prep_override.py`): توزيع الأمثلة على الحصص، واستراتيجية مرحلة، وحذف
    تمارين. سجل واحد للدرس لأن نقل مثال يمسّ حصتين؛ و`data` بالشكل القانوني (`dump_override`) لا يُحفظ فارغًا."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="prep_overrides"
    )
    lesson = models.ForeignKey("curriculum.Lesson", on_delete=models.PROTECT, related_name="prep_overrides")
    data = models.JSONField()

    class Meta:
        ordering = ["lesson_id", "owner_id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "lesson"], name="planning_prep_override_one_per_lesson"),
        ]

    def __str__(self) -> str:
        return f"{self.owner_id} · {self.lesson.code}"


class DeckBuild(TimeStampedModel):
    """آخر عرض طلبه المعلم لحصة: مفتاحه حين طُلب. مخالفته مفتاحَ تحضيره الحالي تعني أن العرض قديم."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deck_builds")
    lesson = models.ForeignKey("curriculum.Lesson", on_delete=models.PROTECT, related_name="deck_builds")
    k = models.PositiveSmallIntegerField()
    key = models.CharField(max_length=200)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "lesson", "k"], name="planning_deck_build_one_per_period"
            ),
            models.CheckConstraint(condition=Q(k__gte=1), name="planning_deck_build_period_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.owner_id} · {self.lesson.code} الحصة {self.k}"


# ───── تشخيص الخطأ: نتيجة الطالب لكل بند (قرار المالك 2026-11-25) ─────

ENROLLMENT_LENGTH = 20
STUDENT_NAME_LENGTH = 30
ITEM_OPTION_COUNT = 4  # رقم الخيار من 0 إلى 3
# الحدود نفسها يفرضها `domain/item_results.py` قبل الكتابة (يحرس تطابقهما `test_student_results.py`)


class SectionStudent(TimeStampedModel):
    """طالب في شعبة معلم: رقم القيد والاسم الأول واسم العائلة فقط، لا اسم رباعي ولا أي بيان آخر (تقليل البيانات)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="section_students"
    )
    section = models.CharField(max_length=20)
    enrollment_no = models.CharField(max_length=ENROLLMENT_LENGTH)
    first_name = models.CharField(max_length=STUDENT_NAME_LENGTH)
    last_name = models.CharField(max_length=STUDENT_NAME_LENGTH)

    class Meta:
        ordering = ["section", "enrollment_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "section", "enrollment_no"], name="planning_student_one_per_enrollment"
            ),
        ]

    def __str__(self) -> str:  # بلا اسم: النص يظهر في السجلات ورسائل الأخطاء
        return f"{self.section} · {self.enrollment_no}"


class ItemResult(TimeStampedModel):
    """اختيار طالب في بند من بنك البنود (الدرس والمثال والبذرة تعيّنه). الصحة ونوع الخطأ مشتقان من البنك عند الحفظ."""

    student = models.ForeignKey(SectionStudent, on_delete=models.CASCADE, related_name="results")
    lesson = models.ForeignKey("curriculum.Lesson", on_delete=models.PROTECT, related_name="item_results")
    example = models.PositiveSmallIntegerField()
    seed = models.PositiveIntegerField()
    choice = models.PositiveSmallIntegerField()
    correct = models.BooleanField()
    error_kind = models.CharField(max_length=16, blank=True, default="")  # مفتاح من ERROR_KINDS، وفارغ للصحيح

    class Meta:
        ordering = ["student_id", "lesson_id", "example", "seed"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "lesson", "example", "seed"], name="planning_result_one_per_item"
            ),
            models.CheckConstraint(
                condition=Q(example__gte=1) & Q(choice__lt=ITEM_OPTION_COUNT),
                name="planning_result_item_valid",
            ),
            models.CheckConstraint(
                condition=Q(correct=True, error_kind="") | (Q(correct=False) & ~Q(error_kind="")),
                name="planning_result_kind_iff_wrong",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} · {self.lesson_id} مثال {self.example}: {self.choice}"


class Assignment(TimeStampedModel):
    """ورقة من باقة حصة كما سُلّمت للمعلم: بنودها لقطات، وتُعاد حين تتغير بصمة تحضيرها (`prep_digest`) وحدها."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assignments")
    lesson = models.ForeignKey("curriculum.Lesson", on_delete=models.PROTECT, related_name="assignments")
    period = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=12)  # مفاتيح `lesson_package.TITLES`
    order = models.PositiveSmallIntegerField()
    prep_digest = models.CharField(max_length=64)
    recipe = models.JSONField()  # العنوان وعدد النسخ في الصفحة وأهداف أمثلة الورقة

    class Meta:
        ordering = ["owner_id", "lesson_id", "period", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "lesson", "period", "kind"], name="planning_assignment_one_per_sheet"
            )
        ]

    def __str__(self) -> str:
        return f"{self.lesson_id}/{self.period}: {self.kind}"


class AssignmentItem(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveSmallIntegerField()
    snapshot = models.JSONField()  # `package_print.entry_snapshot`

    class Meta:
        ordering = ["assignment_id", "order"]
        constraints = [
            models.UniqueConstraint(fields=["assignment", "order"], name="planning_assignment_item_order")
        ]

    def __str__(self) -> str:
        return f"{self.assignment_id}#{self.order}"
