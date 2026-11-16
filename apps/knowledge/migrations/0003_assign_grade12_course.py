"""تعبئة: الوحدات والمبادئ التربوية القائمة تنتمي إلى مقرر الثاني عشر. idempotent."""

from django.db import migrations

SLUG = "g12-sci-s1"


def forwards(apps, schema_editor):
    course = apps.get_model("curriculum", "Course").objects.get(slug=SLUG)
    apps.get_model("knowledge", "UnitProfile").objects.filter(course__isnull=True).update(course=course)
    apps.get_model("knowledge", "PedagogyNote").objects.filter(course__isnull=True).update(course=course)


def backwards(apps, schema_editor):
    apps.get_model("knowledge", "UnitProfile").objects.update(course=None)
    apps.get_model("knowledge", "PedagogyNote").objects.update(course=None)


class Migration(migrations.Migration):
    dependencies = [
        ("curriculum", "0008_seed_grade12_course"),
        ("knowledge", "0002_course_keys"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
