"""تقليص: المقرر مطلوب على الدرس وجدول المواصفات (بعد تعبئة 0011)، والترتيب عددي بالوحدة ثم رقم الدرس.

يزول قيد «الرمز فريد بلا مقرر»: لم يعد درس بلا مقرر ممكنًا.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("curriculum", "0011_backfill_lesson_number_and_course")]

    operations = [
        migrations.RemoveConstraint(model_name="lesson", name="unique_lesson_code_without_course"),
        migrations.AlterField(
            model_name="lesson",
            name="course",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="lessons", to="curriculum.course"
            ),
        ),
        migrations.AlterField(
            model_name="blueprint",
            name="course",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="blueprints", to="curriculum.course"
            ),
        ),
        migrations.AlterModelOptions(
            name="lesson", options={"ordering": ["course_id", "unit", "number", "code"]}
        ),
    ]
