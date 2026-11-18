"""تقليص: درس السجل مطلوب (0005 ربطه وتحقق أن لا سجل بلا درس). حذف `lesson_code` طلب لاحق منفصل."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("planning", "0005_lesson_guard")]

    operations = [
        migrations.AlterField(
            model_name="classoutcomerecord",
            name="lesson",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="class_outcomes", to="curriculum.lesson"
            ),
        ),
        migrations.AlterField(
            model_name="lessonrunrecord",
            name="lesson",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="lesson_runs", to="curriculum.lesson"
            ),
        ),
    ]
