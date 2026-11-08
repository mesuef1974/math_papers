import pytest

from apps.papers import services


@pytest.mark.django_db
def test_quiz_structure_alternates_lessons_and_sums_to_ten(client):
    res = client.get("/api/v1/papers/quiz", {"lessons": "1.1,1.2", "seed": 4})
    assert res.status_code == 200, res.content
    data = res.json()
    assert data["kind"] == "quiz" and data["total_marks"] == 10 and data["lesson_code"] == "1.1,1.2"
    assert [q["kind"] for q in data["questions"]] == ["mcq"] * 4 + ["essay"] * 2
    assert [q["marks"] for q in data["questions"]] == [1, 1, 1, 1, 3, 3]
    assert [q["parts"][0]["lesson"] for q in data["questions"]] == ["1.1", "1.2"] * 3
    assert sum(data["level_marks"].values()) == 10
    assert data["title"].startswith("اختبار قصير: 1.1")
    assert all(len(q["parts"][0]["options"]) == 4 for q in data["questions"][:4])


@pytest.mark.django_db
def test_quiz_single_lesson_deterministic_and_form_b(client):
    a = client.get("/api/v1/papers/quiz", {"lessons": "2.4", "seed": 9}).json()
    again = client.get("/api/v1/papers/quiz", {"lessons": "2.4", "seed": 9}).json()
    b = client.get("/api/v1/papers/quiz", {"lessons": "2.4", "seed": 9, "form": "B"}).json()
    assert a == again and b["form"] == "B" and b["kind"] == "quiz"
    fa = {p["fingerprint"] for q in a["questions"] for p in q["parts"]}
    fb = {p["fingerprint"] for q in b["questions"] for p in q["parts"]}
    assert len(fa) == 6 and not (fa & fb)


@pytest.mark.django_db
def test_quiz_rejects_bad_lessons(client):
    assert client.get("/api/v1/papers/quiz", {"lessons": "1.1,1.2,1.3"}).status_code == 422
    assert client.get("/api/v1/papers/quiz", {"lessons": "9.9"}).status_code == 404


@pytest.mark.django_db
def test_quiz_for_every_lesson_pair_in_a_unit(client):
    codes = sorted(services.available_lessons())
    for first, second in zip(codes, codes[1:]):
        res = client.get("/api/v1/papers/quiz", {"lessons": f"{first},{second}", "seed": 1})
        assert res.status_code == 200, (first, second, res.content)


@pytest.mark.django_db
def test_remedial_and_enrichment_worksheets(client):
    remedial = client.get(
        "/api/v1/papers/worksheet", {"lesson": "2.4", "count": 6, "seed": 2, "purpose": "remedial"}
    )
    assert remedial.status_code == 200
    data = remedial.json()
    assert data["title"].startswith("ورقة علاجية:") and data["level"] == "K"
    assert all(p["level"] == "K" for q in data["questions"] for p in q["parts"])
    enrich = client.get(
        "/api/v1/papers/worksheet", {"lesson": "2.4", "count": 6, "seed": 2, "purpose": "enrichment"}
    ).json()
    assert enrich["title"].startswith("ورقة إثرائية:") and enrich["level"] == "R"
    # 3.5 بلا مستوى سهل: العلاجية غير متاحة
    assert client.get("/api/v1/papers/worksheet", {"lesson": "3.5", "purpose": "remedial"}).status_code == 404


@pytest.mark.django_db
def test_saved_quiz_roundtrip(client):
    import json

    paper = client.get("/api/v1/papers/quiz", {"lessons": "1.1,1.2", "seed": 4}).json()
    recipe = {"kind": "quiz", "lesson_code": "1.1,1.2", "seed": 4, "replacements": []}
    res = client.post(
        "/api/v1/saved", json.dumps({"paper": paper, "recipe": recipe}), content_type="application/json"
    )
    assert res.status_code == 201, res.content
    assert res.json()["kind"] == "quiz" and res.json()["total_marks"] == 10
