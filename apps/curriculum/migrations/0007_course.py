"""توسعة: نموذج المقرر وربط اختياري منه على الدرس وجدول المواصفات. لا تغيير في القيود بعد."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("curriculum", "0006_seed_lesson_3_6_enrichment")]

    operations = [
        migrations.CreateModel(
            name="Course",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=48, unique=True)),
                ("title", models.CharField(max_length=160)),
                ("grade", models.PositiveSmallIntegerField()),
                ("track", models.CharField(blank=True, max_length=60)),
                ("semester", models.PositiveSmallIntegerField()),
                ("edition", models.CharField(blank=True, max_length=32)),
                ("is_current", models.BooleanField(default=False)),
            ],
            options={
                "ordering": ["grade", "track", "semester"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("is_current", True)), fields=("is_current",), name="unique_current_course"
                    )
                ],
            },
        ),
        migrations.AddField(
            model_name="blueprint",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="blueprints",
                to="curriculum.course",
            ),
        ),
        migrations.AddField(
            model_name="lesson",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="lessons",
                to="curriculum.course",
            ),
        ),
    ]
