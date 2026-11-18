"""تعبئة: كل مقرر سبق حقل السنة الأكاديمية كتابُ 2026-2027 (العاشر والثاني عشر، الفصل الأول).

idempotent. منفصلة عن هجرتي المخطط قبلها وبعدها: PostgreSQL يرفض تعديل جدول في المعاملة التي حُدّثت صفوفه فيها.
"""

from django.db import migrations

FIRST_YEAR = "2026-2027"


def forwards(apps, schema_editor):
    Course = apps.get_model("curriculum", "Course")
    Course.objects.filter(academic_year__isnull=True).update(academic_year=FIRST_YEAR)


class Migration(migrations.Migration):
    dependencies = [("curriculum", "0013_sources_schedule_assessment")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
