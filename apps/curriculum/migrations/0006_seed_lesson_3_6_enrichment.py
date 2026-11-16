"""بذر الدرس 3.6 «المعدلات المرتبطة»: درس إثرائي يُدرَّس ولا يُمتحَن (examinable=False كما في 3.4).

غيابه عن 0002 كان يجعل `load_knowledge` يتخطى `lesson_3_6.json`. لا يُضاف إلى جدول المواصفات ولا يُنشأ له مولّد:
`/api/papers/lessons` يعرضه بـ has_generator=false فلا يدخل منتقي ورقة العمل، والتوليد يرفض الدرس بلا مولّد.
"""

from django.db import migrations

CODE = "3.6"
TITLE = "المعدلات المرتبطة"
UNIT = 3


def seed(apps, schema_editor):
    Lesson = apps.get_model("curriculum", "Lesson")
    Lesson.objects.update_or_create(code=CODE, defaults={"title": TITLE, "unit": UNIT, "examinable": False})


class Migration(migrations.Migration):
    dependencies = [("curriculum", "0005_seed_slot_levels")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
