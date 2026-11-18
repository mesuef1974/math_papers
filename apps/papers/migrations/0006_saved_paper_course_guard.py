"""قبل التقليص: يعيد تعبئة 0005 (idempotent) لما حُفظ بعدها، ويوقف الهجرة إن بقيت ورقة بلا مقرر.

الإيقاف يُفشل preDeploy فتبقى النسخة السابقة تعمل ولا تُحذف ورقة؛ الإصلاح تحميل المقرر الناقص ثم إعادة النشر.
"""

import importlib

from django.db import migrations

BACKFILL = importlib.import_module("apps.papers.migrations.0005_backfill_saved_paper_course")


def forwards(apps, schema_editor):
    BACKFILL.forwards(apps, schema_editor)
    orphans = apps.get_model("papers", "SavedPaper").objects.filter(course__isnull=True).count()
    if orphans:
        raise RuntimeError(f"{orphans} ورقة محفوظة بلا مقرر في القاعدة: حمّل مقررها (load_course) ثم أعِد النشر.")


class Migration(migrations.Migration):
    dependencies = [("papers", "0005_backfill_saved_paper_course")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
