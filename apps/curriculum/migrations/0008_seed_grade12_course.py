"""تعبئة: مقرر الثاني عشر هو الحالي، وكل درس وجدول مواصفات قائم يُربط به. idempotent."""

from django.db import migrations

SLUG = "g12-sci-s1"
TITLE = "الرياضيات: الثاني عشر العلمي والتكنولوجي، الفصل الأول"


def forwards(apps, schema_editor):
    Course = apps.get_model("curriculum", "Course")
    course, _ = Course.objects.get_or_create(
        slug=SLUG,
        defaults={"title": TITLE, "grade": 12, "track": "العلمي والتكنولوجي", "semester": 1, "is_current": True},
    )
    apps.get_model("curriculum", "Lesson").objects.filter(course__isnull=True).update(course=course)
    apps.get_model("curriculum", "Blueprint").objects.filter(course__isnull=True).update(course=course)


def backwards(apps, schema_editor):
    apps.get_model("curriculum", "Lesson").objects.update(course=None)
    apps.get_model("curriculum", "Blueprint").objects.update(course=None)
    apps.get_model("curriculum", "Course").objects.filter(slug=SLUG).delete()


class Migration(migrations.Migration):
    dependencies = [("curriculum", "0007_course")]

    operations = [migrations.RunPython(forwards, backwards)]
