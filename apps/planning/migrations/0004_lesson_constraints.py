"""تقليص: الفرادة على الدرس (بمقرره) لا على رمزه النصي، فالرمز نفسه في كتابين سجلان مستقلان."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("planning", "0003_backfill_lesson")]

    operations = [
        migrations.RemoveConstraint(
            model_name="classoutcomerecord", name="planning_outcome_one_per_section_lesson"
        ),
        migrations.RemoveConstraint(model_name="lessonrunrecord", name="planning_run_one_per_start"),
        migrations.AddConstraint(
            model_name="classoutcomerecord",
            constraint=models.UniqueConstraint(
                fields=("owner", "section", "lesson"), name="planning_outcome_one_per_section_lesson_row"
            ),
        ),
        migrations.AddConstraint(
            model_name="lessonrunrecord",
            constraint=models.UniqueConstraint(
                fields=("owner", "section", "lesson", "started_at"), name="planning_run_one_per_lesson_start"
            ),
        ),
    ]
