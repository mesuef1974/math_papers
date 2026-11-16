"""الأوراق عبر المقررات: المولّدات والبذور والبصمات مفاتيحها (مقرر، رمز)، والمسارات تأخذ المقرر (والافتراضي الحالي)."""

import pytest

from apps.curriculum.courses import DEFAULT_COURSE
from apps.curriculum.models import Course, Lesson
from apps.papers import services
from apps.papers.domain.generators import (
    REGISTRY,
    available_lessons,
    generator_version,
    lesson_levels,
)

OTHER = "g10-test"


@pytest.fixture
def other_course(db):
    """مقرر ثانٍ بدرس برمز 1.1 كالثاني عشر، ومولّده مسجَّل باسمه وحده."""
    course = Course.objects.create(slug=OTHER, title="مقرر تجريبي", grade=10, semester=1)
    Lesson.objects.create(course=course, code="1.1", title="درس المقرر الآخر", unit=1)
    REGISTRY[(OTHER, "1.1")] = [REGISTRY[(DEFAULT_COURSE, "1.1")][0]]
    yield course
    del REGISTRY[(OTHER, "1.1")]


def test_registry_is_keyed_by_course(other_course):
    assert available_lessons(OTHER) == {"1.1"}
    assert "1.1" in available_lessons() and len(available_lessons()) > 1
    assert lesson_levels("1.1", course=OTHER)


def test_other_course_generators_do_not_change_grade12_fingerprint():
    before = generator_version()
    REGISTRY[(OTHER, "1.1")] = [REGISTRY[(DEFAULT_COURSE, "1.1")][0]]
    try:
        assert generator_version() == before
        assert generator_version(OTHER) != before
    finally:
        del REGISTRY[(OTHER, "1.1")]


@pytest.mark.django_db
def test_worksheet_resolves_the_lesson_in_the_requested_course(other_course):
    mine = services.build_worksheet("1.1", 3, 11, course=OTHER)
    current = services.build_worksheet("1.1", 3, 11)
    assert mine["title"].endswith("درس المقرر الآخر")
    assert not current["title"].endswith("درس المقرر الآخر")
    assert mine["generator_version"] == generator_version(OTHER)
    assert current["generator_version"] == generator_version()


@pytest.mark.django_db
def test_lesson_without_generator_in_the_course_is_unknown(other_course):
    with pytest.raises(services.UnknownLessonError):
        services.build_worksheet("1.2", 3, 11, course=OTHER)  # 1.2 للثاني عشر وحده
    with pytest.raises(services.UnknownLessonError):
        services.build_worksheet("1.1", 3, 11, course="no-such-course")


def test_bundle_seed_keeps_grade12_form_and_separates_other_courses():
    import random

    legacy = random.Random("77:1.1").randrange(services.MAX_SEED)
    assert services.lesson_seed(77, "1.1") == legacy
    assert services.lesson_seed(77, "1.1", OTHER) != legacy


@pytest.mark.django_db
def test_api_takes_course_and_defaults_to_current(client, other_course):
    mine = client.get("/api/v1/papers/worksheet", {"lesson": "1.1", "seed": 5, "count": 2, "course": OTHER})
    assert mine.status_code == 200 and mine.json()["title"].endswith("درس المقرر الآخر")
    default = client.get("/api/v1/papers/worksheet", {"lesson": "1.1", "seed": 5, "count": 2})
    assert default.status_code == 200 and not default.json()["title"].endswith("درس المقرر الآخر")
    assert client.get("/api/v1/papers/worksheet", {"lesson": "1.1", "course": "x-x"}).status_code == 404
    listed = client.get("/api/v1/lessons", {"course": OTHER}).json()
    assert [row["code"] for row in listed] == ["1.1"] and listed[0]["has_generator"]
    assert len(client.get("/api/v1/lessons").json()) > 1  # الافتراضي: مقرر الثاني عشر
