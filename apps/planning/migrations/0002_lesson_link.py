"""توسعة: ربط نتيجة الصف وتقرير الحصة بالدرس نفسه (ومنه مقرره) بدل رمز نصي يتصادم بين الكتب. اختياري حتى يُملأ."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planning", "0001_class_outcome_and_lesson_run"),
        ("curriculum", "0012_course_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="classoutcomerecord",
            name="lesson",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="class_outcomes",
                to="curriculum.lesson",
            ),
        ),
        migrations.AddField(
            model_name="lessonrunrecord",
            name="lesson",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="lesson_runs",
                to="curriculum.lesson",
            ),
        ),
    ]
