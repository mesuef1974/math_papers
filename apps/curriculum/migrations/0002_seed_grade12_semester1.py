"""بذر دروس الفصل الأول وجدول المواصفات المتوقع 2026-2027. update_or_create يجعلها قابلة للإعادة."""

from django.db import migrations

SLUG = "g12-sci-s1-2026-27-forecast"
LESSONS = [
    ("1.1", "مفهوم النهاية", 1, True),
    ("1.2", "حساب النهايات", 1, True),
    ("1.3", "نهايات الدوال المثلثية", 1, True),
    ("1.4", "الاتصال", 1, True),
    ("2.1", "معدل التغير", 2, True),
    ("2.2", "تعريف المشتقة", 2, True),
    ("2.3", "قواعد الاشتقاق", 2, True),
    ("2.4", "قاعدتا الضرب والقسمة", 2, True),
    ("2.5", "قاعدة السلسلة", 2, True),
    ("2.6", "مشتقات الأسية واللوغاريتمية", 2, True),
    ("2.7", "مشتقات الدوال المثلثية", 2, True),
    ("2.8", "الاشتقاق الضمني", 2, True),
    ("2.9", "المشتقات من الرتب العليا", 2, True),
    ("3.1", "الدوال المتزايدة والمتناقصة", 3, True),
    ("3.2", "القيم القصوى للدوال", 3, True),
    ("3.3", "التقعر ونقاط الانعطاف", 3, True),
    ("3.4", "رسم منحنيات الدوال", 3, False),
    ("3.5", "تطبيقات القيم القصوى", 3, True),
]
MCQ = ["1.1", "1.2", "2.1", "2.2", "2.4", "2.5", "3.1", "3.2", "3.3", "3.5"]
ESSAYS = {
    11: [("1.1", 1), ("1.2", 2), ("1.3", 2), ("1.4", 2), ("2.3", 3)],
    12: [("2.4", 2), ("2.6", 2), ("2.7", 2), ("2.8", 2), ("2.9", 2)],
    13: [("2.1", 1), ("3.1", 2), ("3.2", 2), ("3.3", 3), ("3.5", 2)],
}


def seed(apps, schema_editor):
    Lesson = apps.get_model("curriculum", "Lesson")
    Blueprint = apps.get_model("curriculum", "Blueprint")
    Item = apps.get_model("curriculum", "BlueprintItem")
    lessons = {}
    for code, title, unit, examinable in LESSONS:
        lessons[code], _ = Lesson.objects.update_or_create(
            code=code, defaults={"title": title, "unit": unit, "examinable": examinable}
        )
    blueprint, _ = Blueprint.objects.update_or_create(
        slug=SLUG,
        defaults={
            "title": "اختبار تدريبي: الفصل الأول، 12 علمي وتكنولوجي، 2026-2027",
            "academic_year": "2026-2027",
            "semester": 1,
            "total_marks": 40,
            "is_forecast": True,
        },
    )
    slots = [(number, 1, "mcq", code, 1) for number, code in enumerate(MCQ, start=1)]
    for number, parts in ESSAYS.items():
        slots += [(number, i, "essay", code, marks) for i, (code, marks) in enumerate(parts, start=1)]
    for number, position, kind, code, marks in slots:
        Item.objects.update_or_create(
            blueprint=blueprint,
            question_number=number,
            position=position,
            defaults={"lesson": lessons[code], "kind": kind, "marks": marks},
        )


def unseed(apps, schema_editor):
    apps.get_model("curriculum", "Blueprint").objects.filter(slug=SLUG).delete()


class Migration(migrations.Migration):
    dependencies = [("curriculum", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
