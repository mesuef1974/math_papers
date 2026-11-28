"""تمارين الكتاب بمصدرها: التعبئة تطابق صفوف الملفات، واعتماد المشرف يبقى بعد إعادة التحميل."""

import pytest

from apps.core.models import AuditLog
from apps.knowledge.models import BookExerciseLink, ExerciseGroup
from apps.knowledge.selectors import example_exercises
from apps.knowledge.services import LinkError, approve_lesson_links, load_course, review_exercise_link

COURSES = ("g10-s1", "g12-sci-s1")
BASE = "/api/v1/exercise-links"


def _old(course):
    """القراءة القديمة من `ExerciseGroup`: أرقام كل (درس، نوع، مثال، عمق)."""
    rows = ExerciseGroup.objects.filter(profile__lesson__course__slug=course)
    out: dict = {}
    for code, kind, example, dok, exercises in rows.values_list(
        "profile__lesson__code", "kind", "example", "dok", "exercises"
    ):
        out.setdefault((code, kind, example, dok), set()).update(exercises)
    return out


def _new(course):
    rows = BookExerciseLink.objects.filter(lesson__course__slug=course)
    out: dict = {}
    for code, kind, example, dok, number in rows.values_list(
        "lesson__code", "kind", "example", "dok", "number"
    ):
        out.setdefault((code, kind, example, dok), set()).add(number)
    return out


def _try_link(course="g12-sci-s1"):
    return BookExerciseLink.objects.filter(lesson__course__slug=course, kind="practice").select_related(
        "lesson"
    )[0]


@pytest.mark.django_db
@pytest.mark.parametrize("course", COURSES)
def test_links_match_the_exercise_groups_of_every_lesson(loaded_courses, course):
    assert _new(course) == _old(course) != {}
    assert load_course(course).changed["exercise_links"] == 0  # idempotent


@pytest.mark.django_db
def test_provenance_follows_the_course_declaration(loaded_courses):
    def sources(course, kind):
        rows = BookExerciseLink.objects.filter(lesson__course__slug=course, kind=kind)
        return set(rows.values_list("provenance", flat=True))

    assert sources("g12-sci-s1", "try") == {"teacher"}
    assert sources("g12-sci-s1", "practice") == {"ai_unreviewed"}
    assert sources("g10-s1", "try") == {"guide"}


@pytest.mark.django_db
def test_a_reviewed_correction_survives_reloading(loaded_courses, django_user_model):
    admin = django_user_model.objects.create_superuser("owner", password="x")
    link = _try_link()
    code, number, old = link.lesson.code, link.number, link.example
    new = 1 if old != 1 else 2
    key = {"course": "g12-sci-s1", "lesson": code, "kind": "practice", "number": number}

    assert review_exercise_link(**key, examples=[new], user=admin)
    assert not review_exercise_link(**key, examples=[new], user=admin)
    assert load_course("g12-sci-s1").changed["exercise_links"] == 0

    rows = BookExerciseLink.objects.filter(lesson=link.lesson, kind="practice", number=number)
    assert [(r.example, r.provenance, r.reviewed_by) for r in rows] == [(new, "teacher", admin)]
    assert AuditLog.objects.filter(action="knowledge.exercise_link.review").count() == 1
    with pytest.raises(LinkError):
        review_exercise_link(**key, examples=[39], user=admin)


@pytest.mark.django_db
def test_correcting_a_try_exercise_changes_the_paper_source(loaded_courses, django_user_model):
    admin = django_user_model.objects.create_superuser("owner", password="x")
    link = BookExerciseLink.objects.filter(lesson__course__slug="g10-s1", lesson__code="1.2").first()
    new = 1 if link.example != 1 else 2
    review_exercise_link(
        course="g10-s1", lesson="1.2", kind="try", number=link.number, examples=[new], user=admin
    )
    assert link.number in example_exercises("g10-s1", "1.2", new)
    assert link.number not in example_exercises("g10-s1", "1.2", link.example)


@pytest.mark.django_db
def test_lesson_approval_is_idempotent(loaded_courses, django_user_model):
    admin = django_user_model.objects.create_superuser("owner", password="x")
    code = _try_link().lesson.code
    assert approve_lesson_links(course="g12-sci-s1", lesson=code, user=admin) > 0
    assert approve_lesson_links(course="g12-sci-s1", lesson=code, user=admin) == 0


@pytest.mark.django_db
def test_only_the_superuser_reviews(loaded_courses, client, django_user_model):
    link = _try_link()
    url = f"{BASE}/g12-sci-s1/{link.lesson.code}"
    assert client.get(url).status_code == 401
    client.force_login(django_user_model.objects.create_user("teacher", password="x"))
    assert client.get(url).status_code == 403
    assert client.post(f"{url}/approve").status_code == 403
    client.force_login(django_user_model.objects.create_superuser("owner", password="x"))
    body = client.get(url).json()
    assert body["examples"] and body["exercises"]
    assert any(row["page"] for row in body["exercises"])

    def pending():
        rows = client.get(f"{BASE}/g12-sci-s1").json()
        return next(r for r in rows if r["code"] == link.lesson.code)["pending"]

    before = pending()
    response = client.put(
        f"{url}/practice/{link.number}", {"examples": [link.example]}, content_type="application/json"
    )
    assert response.status_code == 200
    assert pending() == before - 1
    assert client.post(f"{url}/approve").status_code == 200
    assert pending() == 0
