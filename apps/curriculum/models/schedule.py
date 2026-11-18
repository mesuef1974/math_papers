"""الزمن: التقويم الأكاديمي (فصوله وإغلاقاته) والخطة الفصلية للوزارة لكل مقرر (أسابيعها وبنودها وإثرائيّها).

أعداد وتواريخ وأنواع فقط، بلا نص من وثيقة الوزارة؛ عناوين العرض من عندنا. محرك التخطيط (`apps/planning/domain`) يقرأ
هذه الجداول عبر `apps.curriculum.selectors` ولا يقرأ ملفًا.
"""

from __future__ import annotations

from django.db import models

from .catalog import ACADEMIC_YEAR_LENGTH, Course, Lesson
from .sources import SourceDocument


class AcademicCalendar(models.Model):
    """تقويم سنة أكاديمية واحد يشترك فيه كل المقررات."""

    year = models.CharField(max_length=ACADEMIC_YEAR_LENGTH, unique=True)
    weekdays = models.JSONField(default=list)  # أيام الدوام بأسمائها المختصرة: ["sun", "mon", ...]
    grades = models.JSONField(default=list, blank=True)  # الصفوف التي تحقّقنا من تواريخها
    verified_primary = models.BooleanField(default=False)  # أُخذ من نشرة الوزارة نفسها لا من ناقل عنها
    source_note = models.TextField(blank=True)
    notes = models.JSONField(default=list, blank=True)  # ما لم يُعرف بعد

    class Meta:
        ordering = ["-year"]

    def __str__(self) -> str:
        return f"تقويم {self.year}"


class CalendarTerm(models.Model):
    calendar = models.ForeignKey(AcademicCalendar, on_delete=models.CASCADE, related_name="terms")
    semester = models.PositiveSmallIntegerField()
    start = models.DateField()
    end = models.DateField()  # آخر يوم يصلح للتدريس (شامل)

    class Meta:
        ordering = ["calendar_id", "semester"]
        constraints = [
            models.UniqueConstraint(fields=["calendar", "semester"], name="unique_calendar_term"),
            models.CheckConstraint(
                condition=models.Q(end__gte=models.F("start")), name="calendar_term_ordered"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.calendar_id} ف{self.semester}"


class CalendarEvent(models.Model):
    """إغلاق داخل الفصل: اختبارات أو إجازة أو عطلة. grades الفارغة = كل الصفوف."""

    class Kind(models.TextChoices):
        EXAM = "exam", "اختبارات"
        BREAK = "break", "إجازة"
        HOLIDAY = "holiday", "عطلة رسمية"
        OTHER = "other", "أخرى"

    term = models.ForeignKey(CalendarTerm, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    start = models.DateField()
    end = models.DateField()
    label = models.CharField(max_length=120, blank=True)
    grades = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["term_id", "start", "kind"]
        constraints = [
            models.UniqueConstraint(fields=["term", "kind", "start"], name="unique_calendar_event"),
            models.CheckConstraint(
                condition=models.Q(end__gte=models.F("start")), name="calendar_event_ordered"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.start}"


class TermPlan(models.Model):
    """الخطة الفصلية للوزارة لمقرر: الفصل والسنة من المقرر نفسه."""

    course = models.OneToOneField(Course, on_delete=models.PROTECT, related_name="term_plan")
    source = models.ForeignKey(
        SourceDocument, on_delete=models.PROTECT, null=True, blank=True, related_name="term_plans"
    )
    sessions_per_week = models.PositiveSmallIntegerField(default=5)
    # أسبوعا اختبارات تنصّ الخطة على حصص فيهما رغم الإغلاق
    class_during_exams_start = models.DateField(null=True, blank=True)
    class_during_exams_end = models.DateField(null=True, blank=True)
    lost_days = models.JSONField(default=list, blank=True)  # تواريخ ISO لأيام تنقص فيها الحصص
    notes = models.JSONField(default=list, blank=True)  # افتراضات موثّقة وما لم يُعرف

    class Meta:
        ordering = ["course_id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(class_during_exams_start__isnull=True, class_during_exams_end__isnull=True)
                | models.Q(class_during_exams_end__gte=models.F("class_during_exams_start")),
                name="term_plan_exam_window_ordered",
            ),
        ]

    def __str__(self) -> str:
        return f"خطة {self.course_id}"


class PlanWeek(models.Model):
    plan = models.ForeignKey(TermPlan, on_delete=models.CASCADE, related_name="weeks")
    number = models.PositiveSmallIntegerField()
    start = models.DateField()
    end = models.DateField()

    class Meta:
        ordering = ["plan_id", "number"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "number"], name="unique_plan_week"),
            models.CheckConstraint(condition=models.Q(end__gte=models.F("start")), name="plan_week_ordered"),
        ]

    def __str__(self) -> str:
        return f"{self.plan_id} أسبوع {self.number}"


class PlanEntry(models.Model):
    """بند في أسبوع: درس أو مراجعة أو اختبار وحدة... بعدد حصصه. أنواعه هي `ITEM_KINDS` في محرك التخطيط."""

    class Kind(models.TextChoices):
        LESSON = "lesson", "درس"
        REVIEW = "review", "مراجعة"
        QUIZ = "quiz", "اختبار وحدة"
        ORIENTATION = "orientation", "تهيئة"
        EXAM = "exam", "اختبار"
        PROJECT = "project", "مشروع"
        SUPPORT = "support", "دعم"

    class ExamScope(models.TextChoices):
        MIDTERM = "midterm", "منتصف الفصل"
        FINAL = "final", "نهاية الفصل"

    week = models.ForeignKey(PlanWeek, on_delete=models.CASCADE, related_name="entries")
    order = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=12, choices=Kind.choices)
    periods = models.PositiveSmallIntegerField()
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    unit = models.PositiveSmallIntegerField(null=True, blank=True)  # لاختبار الوحدة
    scope = models.CharField(max_length=8, choices=ExamScope.choices, blank=True)  # للمراجعة والاختبار

    class Meta:
        ordering = ["week_id", "order"]
        constraints = [
            models.UniqueConstraint(fields=["week", "order"], name="unique_plan_entry"),
            models.CheckConstraint(condition=models.Q(periods__gte=1), name="plan_entry_has_periods"),
            models.CheckConstraint(
                condition=~models.Q(kind="lesson") | models.Q(lesson__isnull=False),
                name="plan_lesson_entry_has_lesson",
            ),
            models.CheckConstraint(
                condition=~models.Q(kind="quiz") | models.Q(unit__isnull=False),
                name="plan_quiz_entry_has_unit",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.week_id} {self.kind} {self.periods}"


class PlanEnrichment(models.Model):
    """ما تجعله الخطة إثرائيًا لا يدخل الاختبار: الدرس كله (example فارغ) أو مثال منه."""

    plan = models.ForeignKey(TermPlan, on_delete=models.CASCADE, related_name="enrichments")
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="+")
    example = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["plan_id", "lesson_id", "example"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "lesson", "example"], name="unique_plan_enrichment_example"
            ),
            # NULL لا يتساوى في القيد السابق: الدرس الإثرائي كله صف واحد بقيد مستقل
            models.UniqueConstraint(
                fields=["plan", "lesson"],
                condition=models.Q(example__isnull=True),
                name="unique_plan_enrichment_lesson",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.plan_id} {self.lesson_id} {self.example or 'كامل'}"
