"""تعبئة: مقرر كل ورقة محفوظة من وصفتها؛ الوصفة بلا مقرر كانت للثاني عشر (المقرر الحالي الوحيد حتى اليوم). idempotent.

الورقة التي لا يوجد مقرر وصفتها في القاعدة تبقى بلا ربط ولا تُحذف.
"""

from django.db import migrations

LEGACY_COURSE = "g12-sci-s1"


def forwards(apps, schema_editor):
    SavedPaper = apps.get_model("papers", "SavedPaper")
    courses = {course.slug: course.pk for course in apps.get_model("curriculum", "Course").objects.all()}
    for row in SavedPaper.objects.filter(course__isnull=True).only("id", "recipe").iterator():
        slug = (row.recipe or {}).get("course") or LEGACY_COURSE
        if slug in courses:
            SavedPaper.objects.filter(pk=row.pk).update(course_id=courses[slug])


class Migration(migrations.Migration):
    dependencies = [("papers", "0004_saved_paper_course")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
