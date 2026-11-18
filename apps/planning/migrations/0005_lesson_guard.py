"""قبل التقليص: يعيد ربط 0003 (idempotent) لما بقي بلا درس، ويوقف الهجرة إن بقي سجل بلا درس.

الإيقاف يُفشل preDeploy فتبقى النسخة السابقة تعمل ولا يُحذف سجل؛ الإصلاح تحميل مقرر العاشر ثم إعادة النشر.
"""

import importlib

from django.db import migrations

BACKFILL = importlib.import_module("apps.planning.migrations.0003_backfill_lesson")


def forwards(apps, schema_editor):
    BACKFILL.forwards(apps, schema_editor)
    orphans = sum(
        apps.get_model("planning", name).objects.filter(lesson__isnull=True).count()
        for name in ("ClassOutcomeRecord", "LessonRunRecord")
    )
    if orphans:
        raise RuntimeError(f"{orphans} سجل تخطيط بلا درس في القاعدة: حمّل مقرر العاشر (load_course) ثم أعِد النشر.")


class Migration(migrations.Migration):
    dependencies = [("planning", "0004_lesson_constraints")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
