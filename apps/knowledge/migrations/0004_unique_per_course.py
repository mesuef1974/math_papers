"""تقليص: رقم الوحدة ومعرّف المبدأ فريدان مع المقرر لا وحدهما (وبلا مقرر كما كانا)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0003_assign_grade12_course")]

    operations = [
        migrations.AlterModelOptions(name="unitprofile", options={"ordering": ["course_id", "unit"]}),
        migrations.AlterField(model_name="pedagogynote", name="slug", field=models.SlugField(max_length=48)),
        migrations.AlterField(model_name="unitprofile", name="unit", field=models.PositiveSmallIntegerField()),
        migrations.AddConstraint(
            model_name="pedagogynote",
            constraint=models.UniqueConstraint(fields=("course", "slug"), name="unique_pedagogy_per_course"),
        ),
        migrations.AddConstraint(
            model_name="pedagogynote",
            constraint=models.UniqueConstraint(
                condition=models.Q(("course__isnull", True)), fields=("slug",), name="unique_pedagogy_without_course"
            ),
        ),
        migrations.AddConstraint(
            model_name="unitprofile",
            constraint=models.UniqueConstraint(fields=("course", "unit"), name="unique_unit_per_course"),
        ),
        migrations.AddConstraint(
            model_name="unitprofile",
            constraint=models.UniqueConstraint(
                condition=models.Q(("course__isnull", True)), fields=("unit",), name="unique_unit_without_course"
            ),
        ),
    ]
