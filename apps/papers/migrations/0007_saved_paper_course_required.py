"""تقليص: مقرر الورقة المحفوظة مطلوب (0006 ملأه وتحقق أن لا ورقة بلا مقرر)."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("papers", "0006_saved_paper_course_guard")]

    operations = [
        migrations.AlterField(
            model_name="savedpaper",
            name="course",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="saved_papers", to="curriculum.course"
            ),
        ),
    ]
