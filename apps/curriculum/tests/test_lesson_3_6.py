import importlib

import pytest

from apps.curriculum.models import BlueprintItem, Lesson
from apps.knowledge.services import load_knowledge
from apps.papers.domain.generators import available_lessons

migration = importlib.import_module("apps.curriculum.migrations.0006_seed_lesson_3_6_enrichment")

pytestmark = pytest.mark.django_db


def test_lesson_36_seeded_as_enrichment():
    lesson = Lesson.objects.get(code="3.6")
    assert (lesson.title, lesson.unit, lesson.examinable) == ("المعدلات المرتبطة", 3, False)


def test_lesson_36_outside_exam_and_generators():
    assert not BlueprintItem.objects.filter(lesson__code="3.6").exists()
    assert "3.6" not in available_lessons()


def test_seed_is_idempotent():
    from django.apps import apps

    migration.seed(apps, None)
    migration.seed(apps, None)
    assert Lesson.objects.filter(code="3.6").count() == 1


def test_knowledge_loader_loads_lesson_36():
    report = load_knowledge()
    assert report.changed["lessons"] == 0  # الدرس مبذور، فلا يُنشأ ولا يُتخطى
    assert Lesson.objects.get(code="3.6").profile.templates.count() == 15
