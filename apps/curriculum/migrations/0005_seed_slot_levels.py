"""مستوى كل خانة في جدول التوقع وخانات الرسم.

الهدف من 40: سهل 4، متوسط 26، مهارات عليا 10 (قريب من توزيع درجات 2024 و2025)،
وخمس خانات رسم. توزيع الدروس والدرجات لا يتغير.
"""

from django.db import migrations

SLUG = "g12-sci-s1-2026-27-forecast"

# (رقم السؤال، الموضع): (المستوى، رسم)
SLOTS = {
    (1, 1): ("K", True),  # 1.1 نهاية من رسم
    (2, 1): ("K", False),  # 1.2
    (3, 1): ("A", False),  # 2.1
    (4, 1): ("K", False),  # 2.2
    (5, 1): ("A", False),  # 2.4
    (6, 1): ("A", False),  # 2.5
    (7, 1): ("R", True),  # 3.1 شكل f من رسم f′
    (8, 1): ("A", False),  # 3.2
    (9, 1): ("A", False),  # 3.3
    (10, 1): ("A", False),  # 3.5
    (11, 1): ("K", False),  # 1.1
    (11, 2): ("A", False),  # 1.2
    (11, 3): ("A", False),  # 1.3
    (11, 4): ("A", True),  # 1.4 نوع عدم الاتصال من رسم
    (11, 5): ("R", False),  # 2.3
    (12, 1): ("A", False),  # 2.4
    (12, 2): ("A", False),  # 2.6
    (12, 3): ("A", False),  # 2.7
    (12, 4): ("A", False),  # 2.8
    (12, 5): ("R", False),  # 2.9
    (13, 1): ("A", True),  # 2.1 ميل المماس من رسم
    (13, 2): ("A", False),  # 3.1
    (13, 3): ("R", True),  # 3.2 القيم القصوى من رسم f′
    (13, 4): ("A", False),  # 3.3
    (13, 5): ("R", False),  # 3.5
}


def assign(apps, schema_editor):
    Item = apps.get_model("curriculum", "BlueprintItem")
    for (number, position), (level, graph) in SLOTS.items():
        Item.objects.filter(blueprint__slug=SLUG, question_number=number, position=position).update(
            level=level, needs_graph=graph
        )


def clear(apps, schema_editor):
    Item = apps.get_model("curriculum", "BlueprintItem")
    Item.objects.filter(blueprint__slug=SLUG).update(level=None, needs_graph=False)


class Migration(migrations.Migration):
    dependencies = [("curriculum", "0004_blueprint_item_level_graph")]
    operations = [migrations.RunPython(assign, clear)]
