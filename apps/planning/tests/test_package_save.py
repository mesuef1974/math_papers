"""لقطة باقة الحصة (المرحلة 2): الحفظ idempotent، واللقطة تبقى ما لم يتغير التحضير، وحمولة الطباعة يقبلها المخطط."""

import pytest
from django.contrib.auth import get_user_model

from apps.curriculum.courses import GRADE10_SLUG
from apps.papers.api import PrintPayload
from apps.planning.models import Assignment, AssignmentItem
from apps.planning.services import lesson_package_payload, save_lesson_package


@pytest.fixture
def teacher(loaded_courses):
    return get_user_model().objects.create_user("package-teacher")


def _rows():
    return list(Assignment.objects.values_list("pk", "kind")), list(AssignmentItem.objects.values_list("pk"))


@pytest.mark.django_db
def test_saving_twice_changes_nothing_and_a_new_digest_replaces(teacher):
    first = save_lesson_package(teacher, GRADE10_SLUG, "1.1", 2)
    assert first and AssignmentItem.objects.count() >= len(first)
    before = _rows()
    save_lesson_package(teacher, GRADE10_SLUG, "1.1", 2)
    assert _rows() == before
    Assignment.objects.update(prep_digest="old")
    again = save_lesson_package(teacher, GRADE10_SLUG, "1.1", 2)
    assert [a.kind for a in again] == [a.kind for a in first]
    assert Assignment.objects.count() == len(first)
    assert not Assignment.objects.filter(prep_digest="old").exists()


@pytest.mark.django_db
def test_print_payload_passes_the_schema_and_keeps_book_exercises_to_numbers(teacher):
    payload = lesson_package_payload(teacher, GRADE10_SLUG, "1.1", 2, section="10-1")
    parsed = PrintPayload.model_validate(payload)
    assert parsed.package and not parsed.papers
    assert parsed.package.grade.startswith("الصف 10")
    entries = [e for s in parsed.package.sheets for e in s.entries]
    assert {e.source for e in entries} == {"book", "generated", "item"}
    assert all(not e.stem and e.number for e in entries if e.source == "book")
    assert all(e.stem and (e.answer or e.answer_index >= 0) for e in entries if e.source != "book")
