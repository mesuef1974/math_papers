"""توسعة: لغة المقرر ورقم الدرس في وحدته، وقيود سلامة المقرر (صف وفصل وكتاب واحد لكل صف).

الأعمدة الجديدة بقيمة افتراضية في القاعدة (`db_default`) فتكتب النسخة السابقة صفوفًا صالحة أثناء النشر.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("curriculum", "0009_lesson_unique_per_course")]

    operations = [
        migrations.AddField(
            model_name="course",
            name="language",
            field=models.CharField(
                choices=[("ar", "العربية"), ("en", "الإنجليزية")], db_default="ar", default="ar", max_length=2
            ),
        ),
        migrations.AddField(
            model_name="lesson",
            name="number",
            field=models.PositiveSmallIntegerField(db_default=0, default=0),
        ),
        migrations.AddConstraint(
            model_name="course",
            constraint=models.UniqueConstraint(
                fields=("grade", "track", "semester", "edition"), name="unique_course_book"
            ),
        ),
        migrations.AddConstraint(
            model_name="course",
            constraint=models.CheckConstraint(
                condition=models.Q(("grade__gte", 1), ("grade__lte", 12)), name="course_grade_1_to_12"
            ),
        ),
        migrations.AddConstraint(
            model_name="course",
            constraint=models.CheckConstraint(
                condition=models.Q(("semester__gte", 1), ("semester__lte", 3)), name="course_semester_1_to_3"
            ),
        ),
        migrations.AddConstraint(
            model_name="lesson",
            constraint=models.CheckConstraint(condition=models.Q(("unit__gte", 1)), name="lesson_unit_positive"),
        ),
    ]
