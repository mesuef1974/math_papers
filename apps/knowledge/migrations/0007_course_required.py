"""تقليص: المقرر مطلوب على الوحدة والمبدأ التربوي (بعد تعبئة 0006)، ويزول قيدا «فريد بلا مقرر»؛ وترتيب ملفات الدروس عددي."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0006_backfill_course")]

    operations = [
        migrations.RemoveConstraint(model_name="unitprofile", name="unique_unit_without_course"),
        migrations.RemoveConstraint(model_name="pedagogynote", name="unique_pedagogy_without_course"),
        migrations.AlterField(
            model_name="unitprofile",
            name="course",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="units", to="curriculum.course"
            ),
        ),
        migrations.AlterField(
            model_name="pedagogynote",
            name="course",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="pedagogy", to="curriculum.course"
            ),
        ),
        migrations.AlterModelOptions(
            name="pedagogynote", options={"ordering": ["course_id", "order", "slug"]}
        ),
        migrations.AlterModelOptions(
            name="lessonprofile",
            options={"ordering": ["lesson__course_id", "lesson__unit", "lesson__number", "lesson__code"]},
        ),
    ]
