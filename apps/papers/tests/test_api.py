import random

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
    res = client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": 7})
    assert res.status_code == 200
    data = res.json()
    questions = data["questions"]
    assert len(questions) == 13
    assert sum(q["marks"] for q in questions) == 40
    assert sum(data["level_marks"].values()) == 40
    assert [q["marks"] for q in questions[10:]] == [10, 10, 10]
    assert all(len(q["parts"][0]["options"]) == 4 for q in questions[:10])
    text_parts = [q["parts"][0] for q in questions[:10] if not q["parts"][0]["option_graphs"]]
    assert all(part["answer"] in part["options"] for part in text_parts)


@pytest.mark.django_db
def test_same_seed_same_paper_and_new_seed_differs(client):
    params = {"blueprint": SLUG, "seed": 11}
    first = client.get("/api/v1/papers/exam", params).json()
    second = client.get("/api/v1/papers/exam", params).json()
    other = client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": 12}).json()
    assert first == second
    assert first["questions"] != other["questions"]


@pytest.mark.django_db
@pytest.mark.parametrize("seed", range(40))
def test_exam_has_no_repeated_stem(client, seed):
    data = client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": seed}).json()
    stems = [(p["stem"], str(p["graph"])) for q in data["questions"] for p in q["parts"]]
    assert len(stems) == len(set(stems))


@pytest.mark.django_db
@pytest.mark.parametrize("lesson", sorted(available_lessons()))
def test_worksheet_reaches_maximum_size_for_every_lesson(client, lesson):
    res = client.get("/api/v1/papers/worksheet", {"lesson": lesson, "count": 20, "seed": 3})
    assert res.status_code == 200
    questions = res.json()["questions"]
    assert len(questions) == 20
    assert {q["parts"][0]["lesson"] for q in questions} == {lesson}


@pytest.mark.django_db
def test_rejects_bad_input(client):
    assert client.get("/api/v1/papers/exam", {"blueprint": "none"}).status_code == 404
    assert client.get("/api/v1/papers/worksheet", {"lesson": "3.4"}).status_code == 404
    assert client.get("/api/v1/papers/worksheet", {"lesson": "2.4", "count": 500}).status_code == 422
    assert client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": -1}).status_code == 422


@pytest.mark.django_db
def test_lessons_flag_missing_generator(client):
    rows = {row["code"]: row for row in client.get("/api/v1/lessons").json()}
    assert rows["3.4"]["has_generator"] is False
    assert rows["3.3"]["has_generator"] is True


@pytest.mark.django_db
def test_graph_is_served_with_the_part(client):
    for seed in range(30):
        data = client.get("/api/v1/papers/worksheet", {"lesson": "1.1", "count": 6, "seed": seed}).json()
        graphs = [p["graph"] for q in data["questions"] for p in q["parts"] if p["graph"]]
        if graphs:
            assert set(graphs[0]) == {"window", "label", "curves", "dots", "asymptotes", "lines"}
            return
    pytest.fail("لم يظهر رسم في 30 ورقة لدرس 1.1")


@pytest.mark.django_db
def test_graph_options_are_shuffled_with_their_answer(client):
    from apps.papers import services
    from apps.papers.domain.generators import REGISTRY

    builder = next(fn for fn in REGISTRY["3.1"] if fn.__name__ == "function_from_derivative_graph")
    seen = set()
    for seed in range(40):
        rng = random.Random(seed)
        problem = builder(rng)
        slot = services.PartSlot("", "3.1", "", "mcq", 1)
        part = services.render_part(problem, slot, rng)
        assert len(part["option_graphs"]) == 4 and part["options"] == ["", "", "", ""]
        index = services.OPTION_LABELS.index(part["answer"][-2])
        assert part["option_graphs"][index] == problem.option_graphs[0]
        seen.add(index)
    assert len(seen) > 1


@pytest.mark.django_db
def test_worksheet_respects_requested_level(client):
    rows = {row["code"]: row for row in client.get("/api/v1/lessons").json()}
    for code, row in rows.items():
        for level in row["levels"]:
            data = client.get(
                "/api/v1/papers/worksheet", {"lesson": code, "count": 6, "seed": 2, "level": level}
            ).json()
            assert {q["parts"][0]["level"] for q in data["questions"]} == {level}, (code, level)
            assert data["level"] == level
        for level in {"K", "A", "R"} - set(row["levels"]):
            res = client.get("/api/v1/papers/worksheet", {"lesson": code, "level": level})
            assert res.status_code == 404


@pytest.mark.django_db
def test_worksheet_rejects_unknown_level(client):
    assert client.get("/api/v1/papers/worksheet", {"lesson": "2.4", "level": "X"}).status_code == 422


@pytest.mark.django_db
@pytest.mark.parametrize("seed", range(12))
def test_exam_levels_and_graphs_follow_blueprint(client, seed):
    data = client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": seed}).json()
    assert data["level_marks"] == {"K": 4, "A": 26, "R": 10}
    parts = [part for q in data["questions"] for part in q["parts"]]
    graphs = [part for part in parts if part["graph"] or part["option_graphs"]]
    assert len(graphs) >= 3
    units: dict[str, int] = {}
    for part in parts:
        units[part["lesson"][0]] = units.get(part["lesson"][0], 0) + part["marks"]
    assert units == {"1": 9, "2": 18, "3": 13}


@pytest.mark.django_db
def test_every_blueprint_slot_has_a_matching_variant():
    from apps.papers.domain.generators import variants

    for item in BlueprintItem.objects.filter(blueprint__slug=SLUG).select_related("lesson"):
        assert item.level, item
        assert variants(item.lesson.code, item.kind, item.level, item.needs_graph), item
