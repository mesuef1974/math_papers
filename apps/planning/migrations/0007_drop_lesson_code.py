"""تقليص أخير: حذف `lesson_code` من السجلين. الدرس المرتبط (مطلوب منذ 0006) مصدر الرمز الوحيد.

العكس يعيد العمود فارغًا لا بقيمه: الرمز يُستعاد من `lesson.code`.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("planning", "0006_lesson_required"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="classoutcomerecord",
            name="lesson_code",
        ),
        migrations.RemoveField(
            model_name="lessonrunrecord",
            name="lesson_code",
        ),
    ]
