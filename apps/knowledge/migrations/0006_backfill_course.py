"""تعبئة: أي وحدة أو مبدأ تربوي بقي بلا مقرر يُربط بمقرر الثاني عشر (كل ما سبق المقررات كان له). idempotent."""

from django.db import migrations

LEGACY_COURSE = "g12-sci-s1"


def forwards(apps, schema_editor):
    UnitProfile = apps.get_model("knowledge", "UnitProfile")
    PedagogyNote = apps.get_model("knowledge", "PedagogyNote")
    orphans = UnitProfile.objects.filter(course__isnull=True).exists() or PedagogyNote.objects.filter(
        course__isnull=True
    ).exists()
    if not orphans:
        return
    course = apps.get_model("curriculum", "Course").objects.filter(slug=LEGACY_COURSE).first()
    if course is None:
        raise RuntimeError(f"صفوف بلا مقرر والمقرر {LEGACY_COURSE} غير موجود: اربطها يدويًا ثم أعد الهجرة")
    UnitProfile.objects.filter(course__isnull=True).update(course=course)
    PedagogyNote.objects.filter(course__isnull=True).update(course=course)


class Migration(migrations.Migration):
    dependencies = [
        ("knowledge", "0005_canonical_contract"),
        ("curriculum", "0012_course_required"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
