"""الكتالوج: المقرر (كتاب واحد لسنة أكاديمية) ودروسه. حقول وقيود فقط."""

from __future__ import annotations

from django.db import models

ACADEMIC_YEAR_LENGTH = 9  # «2026-2027»


class Course(models.Model):
    """مقرر: كتاب واحد (صف ومسار وفصل وسنة أكاديمية وطبعة). مفتاح الدروس والوحدات والمصادر والخطط والاختبارات."""

    class Language(models.TextChoices):
        ARABIC = "ar", "العربية"
        ENGLISH = "en", "الإنجليزية"

    slug = models.SlugField(max_length=48, unique=True)
    title = models.CharField(max_length=160)
    grade = models.PositiveSmallIntegerField()
    track = models.CharField(max_length=60, blank=True)
    semester = models.PositiveSmallIntegerField()
    # السنة التي يُدرَّس فيها الكتاب: طبعة السنة التالية مقرر جديد، ويبقى القديم بأوراقه المحفوظة سليمًا.
    # nullable في التوسعة فقط (الهجرة 0013)، ومطلوب بعد تعبئته (0015).
    academic_year = models.CharField(max_length=ACADEMIC_YEAR_LENGTH)
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
            # الكتاب الواحد صف واحد: لا مقرران بالسنة والصف والمسار والفصل والطبعة نفسها
            models.UniqueConstraint(
                fields=["academic_year", "grade", "track", "semester", "edition"],
                name="unique_course_book_year",
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
