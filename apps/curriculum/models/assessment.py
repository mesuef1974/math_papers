"""التقييم: جداول المواصفات (الرسمية والمتوقعة) للاختبارات الأربعة في السنة، والاختبارات السابقة أرقامًا لا نصًّا."""

from __future__ import annotations

from django.db import models

from .catalog import ACADEMIC_YEAR_LENGTH, Course, Lesson
from .sources import SourceDocument


class Assessment(models.TextChoices):
    """الاختبارات الأربعة في السنة: منتصف كل فصل ونهايته (والفصل من المقرر)."""

    MIDTERM = "midterm", "منتصف الفصل"
    FINAL = "final", "نهاية الفصل"


class Scope(models.TextChoices):
    """نطاق الاختبار من منهج الفصل: الوزارة تصدر للنهائي أحيانًا «الفصل كاملًا» وأحيانًا «النصف الثاني»."""

    FULL = "full", "الفصل كاملًا"
    FIRST_HALF = "first_half", "النصف الأول"
    SECOND_HALF = "second_half", "النصف الثاني"


class AssessmentSlot(models.Model):
    """خانة سؤال: فرع يقيس درسًا بنوع ودرجة ومستوى. مشتركة بين جدول المواصفات والاختبار السابق."""

    class Kind(models.TextChoices):
        MCQ = "mcq", "موضوعي"
        ESSAY = "essay", "مقالي"

    class Level(models.TextChoices):
        EASY = "K", "سهل"
        MEDIUM = "A", "متوسط"
        HIGHER = "R", "مهارات عليا"

    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="+")
    question_number = models.PositiveSmallIntegerField()
    position = models.PositiveSmallIntegerField(default=1)
    kind = models.CharField(max_length=5, choices=Kind.choices)
    marks = models.PositiveSmallIntegerField()
    # فارغ = أي مستوى. التوسعة nullable حتى تعمل النسخة السابقة أثناء النشر.
    level = models.CharField(max_length=1, choices=Level.choices, null=True, blank=True)
    needs_graph = models.BooleanField(default=False, db_default=False)

    class Meta:
        abstract = True
        ordering = ["question_number", "position"]


class Blueprint(models.Model):
    """جدول مواصفات اختبار. is_forecast يعني أنه توقع غير رسمي (الوزارة لا تصدر جداول للثانوية العامة)."""

    slug = models.SlugField(max_length=64, unique=True)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="blueprints")
    title = models.CharField(max_length=160)
    academic_year = models.CharField(max_length=ACADEMIC_YEAR_LENGTH)
    semester = models.PositiveSmallIntegerField()
    assessment = models.CharField(
        max_length=8, choices=Assessment.choices, default=Assessment.FINAL, db_default=Assessment.FINAL
    )
    scope = models.CharField(max_length=11, choices=Scope.choices, default=Scope.FULL, db_default=Scope.FULL)
    total_marks = models.PositiveSmallIntegerField()
    is_forecast = models.BooleanField(default=True)
    source = models.ForeignKey(
        SourceDocument, on_delete=models.PROTECT, null=True, blank=True, related_name="blueprints"
    )

    class Meta:
        ordering = ["-academic_year", "semester", "assessment"]
        permissions = [("generate_paper", "يولّد اختبارات وأوراق عمل")]
        constraints = [
            # جدول رسمي واحد لكل اختبار ونطاق؛ التوقعات قد تتعدد
            models.UniqueConstraint(
                fields=["course", "academic_year", "semester", "assessment", "scope"],
                condition=models.Q(is_forecast=False),
                name="unique_official_blueprint",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class BlueprintItem(AssessmentSlot):
    blueprint = models.ForeignKey(Blueprint, on_delete=models.CASCADE, related_name="items")
    # مجموعة دروس الوزارة التي تملك الخانة (مثل «2a»): النموذج ب يبدّل دروس المجموعة بين خاناتها. فارغ = بلا تدوير.
    group = models.CharField(max_length=16, blank=True, default="", db_default="")

    class Meta(AssessmentSlot.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["blueprint", "question_number", "position"], name="unique_blueprint_slot"
            )
        ]

    def __str__(self) -> str:
        return f"{self.question_number}.{self.position} {self.lesson_id}"


class PastExam(models.Model):
    """اختبار وزاري سابق مسقَطًا على دروس المقرر: أرقام فقط. ما لم يُسقَط على درس تُحفظ درجاته في unmapped_marks."""

    class Attempt(models.TextChoices):
        MAIN = "main", "الدور الأول"
        MAKEUP = "makeup", "الدور الثاني"

    slug = models.SlugField(max_length=64, unique=True)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="past_exams")
    source = models.ForeignKey(
        SourceDocument, on_delete=models.PROTECT, null=True, blank=True, related_name="past_exams"
    )
    academic_year = models.CharField(max_length=ACADEMIC_YEAR_LENGTH)  # سنة الاختبار لا سنة المقرر
    semester = models.PositiveSmallIntegerField()
    assessment = models.CharField(max_length=8, choices=Assessment.choices)
    scope = models.CharField(max_length=11, choices=Scope.choices, default=Scope.FULL)
    attempt = models.CharField(max_length=6, choices=Attempt.choices, default=Attempt.MAIN)
    total_marks = models.PositiveSmallIntegerField()
    unmapped_marks = models.PositiveSmallIntegerField(default=0)  # أسئلة من دروس ليست في طبعة المقرر

    class Meta:
        ordering = ["course_id", "-academic_year", "semester", "assessment", "attempt"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "academic_year", "semester", "assessment", "scope", "attempt"],
                name="unique_past_exam",
            ),
            models.CheckConstraint(
                condition=models.Q(unmapped_marks__lte=models.F("total_marks")),
                name="past_exam_unmapped_le_total",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.course_id} {self.academic_year} ف{self.semester} {self.get_assessment_display()}"


class PastExamItem(AssessmentSlot):
    exam = models.ForeignKey(PastExam, on_delete=models.CASCADE, related_name="items")
    dok = models.PositiveSmallIntegerField(null=True, blank=True)  # عمق المعرفة 1-4 إن عُرف

    class Meta(AssessmentSlot.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "question_number", "position"], name="unique_past_exam_slot"
            ),
            models.CheckConstraint(
                condition=models.Q(dok__isnull=True) | models.Q(dok__gte=1, dok__lte=4),
                name="past_exam_dok_1_to_4",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.exam_id} {self.question_number}.{self.position}"
