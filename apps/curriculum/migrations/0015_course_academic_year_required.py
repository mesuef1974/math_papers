"""عقد: السنة الأكاديمية مطلوبة بعد تعبئتها (0014)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("curriculum", "0014_backfill_course_academic_year")]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="academic_year",
            field=models.CharField(max_length=9),
        ),
    ]
