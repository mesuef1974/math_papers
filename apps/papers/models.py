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
