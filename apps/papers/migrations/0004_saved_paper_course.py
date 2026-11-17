"""توسعة: مقرر الورقة المحفوظة عمودًا (كان في الوصفة وحدها، وفارغًا لأوراق المقرر الحالي). اختياري حتى يُملأ."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("papers", "0003_saved_paper_quiz"),
        ("curriculum", "0012_course_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="savedpaper",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="saved_papers",
                to="curriculum.course",
            ),
        ),
    ]
