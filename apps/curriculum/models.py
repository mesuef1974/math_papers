"""نماذج المنهج: الدروس وجداول المواصفات. حقول وقيود فقط."""

from __future__ import annotations

from django.db import models


class Course(models.Model):
    """مقرر: كتاب واحد (صف ومسار وفصل وطبعة). مفتاح الدروس والوحدات والمبادئ التربوية مع رمزها."""

    class Language(models.TextChoices):
        ARABIC = "ar", "العربية"
        ENGLISH = "en", "الإنجليزية"

    slug = models.SlugField(max_length=48, unique=True)
    title = models.CharField(max_length=160)
    grade = models.PositiveSmallIntegerField()
    track = models.CharField(max_length=60, blank=True)
    semester = models.PositiveSmallIntegerField()
    edition = models.CharField(max_length=32, blank=True)
    # لغة الكتاب: تحدد اتجاه العرض ومعجم الاستخراج. db_default كي تكتب النسخة السابقة صفوفًا صالحة أثناء النشر.
    language = models.CharField(
        max_length=2, choices=Language.choices, default=Language.ARABIC, db_default=Language.ARABIC
    )
    # المقرر الذي تفترضه الواجهة والمسارات حين لا يُحدَّد مقرر؛ واحد على الأكثر
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ["grade", "track", "semester"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_current"], condition=models.Q(is_current=True), name="unique_current_course"
            ),
            # الكتاب الواحد صف واحد: لا مقرران بالصف والمسار والفصل والطبعة نفسها
            models.UniqueConstraint(
                fields=["grade", "track", "semester", "edition"], name="unique_course_book"
            ),
            models.CheckConstraint(
                condition=models.Q(grade__gte=1, grade__lte=12), name="course_grade_1_to_12"
            ),
            models.CheckConstraint(
                condition=models.Q(semester__gte=1, semester__lte=3), name="course_semester_1_to_3"
            ),
        ]

    def __str__(self) -> str:
        return self.title


class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="lessons")
    code = models.CharField(max_length=8)
    title = models.CharField(max_length=120)
    unit = models.PositiveSmallIntegerField()
    # رقم الدرس في وحدته (الجزء الثاني من الرمز): الترتيب عددي، فالدرس 2.10 بعد 2.9 لا قبل 2.2.
    number = models.PositiveSmallIntegerField(default=0, db_default=0)
    examinable = models.BooleanField(default=True)

    class Meta:
        ordering = ["course_id", "unit", "number", "code"]
        constraints = [
            models.UniqueConstraint(fields=["course", "code"], name="unique_lesson_per_course"),
            models.CheckConstraint(condition=models.Q(unit__gte=1), name="lesson_unit_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.title}"


class Blueprint(models.Model):
    """جدول مواصفات. is_forecast يعني أنه توقع غير رسمي، فالوزارة لا تصدر جداول للثانوية العامة."""

    slug = models.SlugField(max_length=64, unique=True)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="blueprints")
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
