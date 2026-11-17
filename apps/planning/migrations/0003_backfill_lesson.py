"""تعبئة: السجلات السابقة للربط كانت كلها للعاشر (المقرر الوحيد الذي للتخطيط فهرسه)، فتُربط بدرسه ذي الرمز نفسه.

السجل الذي لا درس له في القاعدة (المقرر لم يُحمَّل بعد) يبقى بلا ربط ولا يُحذف. idempotent.
"""

from django.db import migrations

LEGACY_COURSE = "g10-s1"


def forwards(apps, schema_editor):
    lessons = {
        lesson.code: lesson.pk
        for lesson in apps.get_model("curriculum", "Lesson").objects.filter(course__slug=LEGACY_COURSE)
    }
    for name in ("ClassOutcomeRecord", "LessonRunRecord"):
        model = apps.get_model("planning", name)
        for code in model.objects.filter(lesson__isnull=True).values_list("lesson_code", flat=True).distinct():
            if code in lessons:
                model.objects.filter(lesson__isnull=True, lesson_code=code).update(lesson_id=lessons[code])


class Migration(migrations.Migration):
    dependencies = [("planning", "0002_lesson_link")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
