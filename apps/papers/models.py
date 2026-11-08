"""نموذج نحيل: إعدادات ترويسة الطباعة لكل معلم. المنطق في services.py."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel

DEFAULT_SUBJECT = "الرياضيات"
DEFAULT_GRADE = "الصف 12: المسار العلمي / المسار التكنولوجي"
DEFAULT_EXAM_MINUTES = 150  # غلاف اختبار الشهادة الثانوية 2025: ساعتان ونصف
DEFAULT_EXAM_INSTRUCTIONS = (
    "أجب عن جميع الأسئلة. اختر الإجابة الصحيحة في الأسئلة الموضوعية بوضع علامة × في المربع المجاور لها، "
    "وبيّن خطوات الحل في الأسئلة المقالية."
)
DEFAULT_WORKSHEET_INSTRUCTIONS = "حل المسائل الآتية مبيّنًا خطوات الحل."


class PrintProfile(TimeStampedModel):
    """ترويسة الطباعة التي يملؤها المعلم مرة وتظهر على كل ورقة يطبعها."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="print_profile"
    )
    school = models.CharField(max_length=160, blank=True)
    teacher_name = models.CharField(max_length=120, blank=True)
    subject = models.CharField(max_length=80, default=DEFAULT_SUBJECT)
    grade = models.CharField(max_length=120, default=DEFAULT_GRADE)
    exam_minutes = models.PositiveSmallIntegerField(default=DEFAULT_EXAM_MINUTES)
    exam_instructions = models.CharField(max_length=500, default=DEFAULT_EXAM_INSTRUCTIONS)
    worksheet_instructions = models.CharField(max_length=500, default=DEFAULT_WORKSHEET_INSTRUCTIONS)

    def __str__(self) -> str:
        return f"ترويسة {self.user_id}"


class SavedPaper(TimeStampedModel):
    """ورقة حفظها المعلم: لقطة كاملة تُطبع كما كانت ولو تغيّرت المولّدات، ووصفة تشرح كيف وُلّدت وما استُبدل.

    الأعمدة المختصرة (الدرس، البذرة، العدد...) منسوخة من اللقطة لتُعرض القائمة دون تحميل اللقطات.
    """

    class Kind(models.TextChoices):
        EXAM = "exam", "اختبار"
        WORKSHEET = "worksheet", "ورقة عمل"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_papers")
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    blueprint = models.CharField(max_length=80, blank=True)
    lesson_code = models.CharField(max_length=10, blank=True)
    seed = models.PositiveIntegerField()
    total_marks = models.PositiveSmallIntegerField(default=0)
    question_count = models.PositiveSmallIntegerField(default=0)
    replacement_count = models.PositiveSmallIntegerField(default=0)
    generator_version = models.CharField(max_length=12, blank=True)
    recipe_hash = models.CharField(max_length=40)
    snapshot = models.JSONField()
    recipe = models.JSONField()

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "recipe_hash"], name="papers_savedpaper_owner_recipe_uniq"
            )
        ]
        indexes = [models.Index(fields=["owner", "-updated_at"])]

    def __str__(self) -> str:
        return self.title
