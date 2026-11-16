"""تقليص: رمز الدرس لم يعد فريدًا وحده بل مع المقرر (وللدرس بلا مقرر برمزه كما كان)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("curriculum", "0008_seed_grade12_course")]

    operations = [
        migrations.AlterModelOptions(name="lesson", options={"ordering": ["course_id", "code"]}),
        migrations.AlterField(model_name="lesson", name="code", field=models.CharField(max_length=8)),
        migrations.AddConstraint(
            model_name="lesson",
            constraint=models.UniqueConstraint(fields=("course", "code"), name="unique_lesson_per_course"),
        ),
        migrations.AddConstraint(
            model_name="lesson",
            constraint=models.UniqueConstraint(
                condition=models.Q(("course__isnull", True)), fields=("code",), name="unique_lesson_code_without_course"
            ),
        ),
    ]
