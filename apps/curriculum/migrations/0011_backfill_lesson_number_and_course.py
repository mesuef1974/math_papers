"""تعبئة: رقم الدرس من رمزه، وربط أي درس أو جدول مواصفات بقي بلا مقرر بمقرر الثاني عشر (كل ما سبق المقررات كان له).

idempotent. منفصلة عن هجرتي المخطط قبلها وبعدها: PostgreSQL يرفض تعديل جدول في المعاملة التي حُدّثت صفوفه فيها.
"""

import re

from django.db import migrations

LEGACY_COURSE = "g12-sci-s1"
CODE = re.compile(r"^\d{1,2}\.(\d{1,2})$")


def forwards(apps, schema_editor):
    Course = apps.get_model("curriculum", "Course")
    Lesson = apps.get_model("curriculum", "Lesson")
    Blueprint = apps.get_model("curriculum", "Blueprint")

    for lesson in Lesson.objects.filter(number=0):
        match = CODE.match(lesson.code)
        if match:
            Lesson.objects.filter(pk=lesson.pk).update(number=int(match.group(1)))

    orphans = Lesson.objects.filter(course__isnull=True).exists() or Blueprint.objects.filter(
        course__isnull=True
    ).exists()
    if not orphans:
        return
    course = Course.objects.filter(slug=LEGACY_COURSE).first()
    if course is None:
        raise RuntimeError(f"صفوف بلا مقرر والمقرر {LEGACY_COURSE} غير موجود: اربطها يدويًا ثم أعد الهجرة")
    Lesson.objects.filter(course__isnull=True).update(course=course)
    Blueprint.objects.filter(course__isnull=True).update(course=course)


class Migration(migrations.Migration):
    dependencies = [("curriculum", "0010_course_language_lesson_number")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
