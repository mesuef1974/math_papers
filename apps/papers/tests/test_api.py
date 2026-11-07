import pytest

from apps.curriculum.models import Blueprint, BlueprintItem
from apps.papers.domain.generators import available_lessons

SLUG = "g12-sci-s1-2026-27-forecast"
FORECAST = {
    "1.1": 2,
    "1.2": 3,
    "1.3": 2,
    "1.4": 2,
    "2.1": 2,
    "2.2": 1,
    "2.3": 3,
    "2.4": 3,
    "2.5": 1,
    "2.6": 2,
    "2.7": 2,
    "2.8": 2,
    "2.9": 2,
    "3.1": 3,
    "3.2": 3,
    "3.3": 4,
    "3.5": 3,
}


@pytest.mark.django_db
def test_blueprint_matches_forecast():
    blueprint = Blueprint.objects.get(slug=SLUG)
    marks: dict[str, int] = {}
    for item in BlueprintItem.objects.filter(blueprint=blueprint).select_related("lesson"):
        marks[item.lesson.code] = marks.get(item.lesson.code, 0) + item.marks
    assert marks == FORECAST
    assert sum(marks.values()) == blueprint.total_marks == 40


@pytest.mark.django_db
def test_exam_shape_and_marks(client):
    res = client.get("/api/papers/exam", {"blueprint": SLUG, "seed": 7})
    assert res.status_code == 200
    data = res.json()
    questions = data["questions"]
    assert len(questions) == 13
    assert sum(q["marks"] for q in questions) == 40
    assert sum(data["level_marks"].values()) == 40
    assert [q["marks"] for q in questions[10:]] == [10, 10, 10]
    assert all(len(q["parts"][0]["options"]) == 4 for q in questions[:10])
    assert all(q["parts"][0]["answer"] in q["parts"][0]["options"] for q in questions[:10])


@pytest.mark.django_db
def test_same_seed_same_paper_and_new_seed_differs(client):
    params = {"blueprint": SLUG, "seed": 11}
    first = client.get("/api/papers/exam", params).json()
    second = client.get("/api/papers/exam", params).json()
    other = client.get("/api/papers/exam", {"blueprint": SLUG, "seed": 12}).json()
    assert first == second
    assert first["questions"] != other["questions"]


@pytest.mark.django_db
@pytest.mark.parametrize("seed", range(40))
def test_exam_has_no_repeated_stem(client, seed):
    data = client.get("/api/papers/exam", {"blueprint": SLUG, "seed": seed}).json()
    stems = [p["stem"] for q in data["questions"] for p in q["parts"]]
    assert len(stems) == len(set(stems))


@pytest.mark.django_db
@pytest.mark.parametrize("lesson", sorted(available_lessons()))
def test_worksheet_reaches_maximum_size_for_every_lesson(client, lesson):
    res = client.get("/api/papers/worksheet", {"lesson": lesson, "count": 20, "seed": 3})
    assert res.status_code == 200
    questions = res.json()["questions"]
    assert len(questions) == 20
    assert {q["parts"][0]["lesson"] for q in questions} == {lesson}


@pytest.mark.django_db
def test_rejects_bad_input(client):
    assert client.get("/api/papers/exam", {"blueprint": "none"}).status_code == 404
    assert client.get("/api/papers/worksheet", {"lesson": "3.4"}).status_code == 404
    assert client.get("/api/papers/worksheet", {"lesson": "2.4", "count": 500}).status_code == 422
    assert client.get("/api/papers/exam", {"blueprint": SLUG, "seed": -1}).status_code == 422


@pytest.mark.django_db
def test_lessons_flag_missing_generator(client):
    rows = {row["code"]: row for row in client.get("/api/lessons").json()}
    assert rows["3.4"]["has_generator"] is False
    assert rows["3.3"]["has_generator"] is True


@pytest.mark.django_db
def test_graph_is_served_with_the_part(client):
    for seed in range(30):
        data = client.get("/api/papers/worksheet", {"lesson": "1.1", "count": 6, "seed": seed}).json()
        graphs = [p["graph"] for q in data["questions"] for p in q["parts"] if p["graph"]]
        if graphs:
            assert set(graphs[0]) == {"window", "label", "curves", "dots", "asymptotes", "lines"}
            return
    pytest.fail("لم يظهر رسم في 30 ورقة لدرس 1.1")
