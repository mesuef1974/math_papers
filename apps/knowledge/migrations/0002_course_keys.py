"""توسعة: ربط اختياري بالمقرر على الوحدة والمبدأ التربوي."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("curriculum", "0007_course"),
        ("knowledge", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedagogynote",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pedagogy",
                to="curriculum.course",
            ),
        ),
        migrations.AddField(
            model_name="unitprofile",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="units",
                to="curriculum.course",
            ),
        ),
    ]
