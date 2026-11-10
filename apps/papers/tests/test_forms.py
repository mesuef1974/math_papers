import pytest

SLUG = "g12-sci-s1-2026-27-forecast"


def shape(paper):
    return [
        (
            q["number"],
            q["kind"],
            q["marks"],
            [(p["label"], p["lesson"], p["marks"], p["slot"]) for p in q["parts"]],
        )
        for q in paper["questions"]
    ]


def fingerprints(paper):
    return {p["fingerprint"] for q in paper["questions"] for p in q["parts"]}


@pytest.mark.django_db
def test_form_b_has_same_structure_and_no_shared_problem(client):
    a = client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": 21}).json()
    b = client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": 21, "form": "B"}).json()
    assert a["form"] == "A" and b["form"] == "B"
    assert shape(a) == shape(b)
    assert b["seed"] == a["seed"] and b["title"] == a["title"] and b["total_marks"] == 40
    assert not (fingerprints(a) & fingerprints(b))
    pairs = [
        (pa, pb) for qa, qb in zip(a["questions"], b["questions"]) for pa, pb in zip(qa["parts"], qb["parts"])
    ]
    same_variant = sum(pa["variant"] == pb["variant"] for pa, pb in pairs)
    assert same_variant >= 0.85 * len(pairs)
    assert sum(b["level_marks"].values()) == 40
    again = client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": 21, "form": "B"}).json()
    assert again == b


@pytest.mark.django_db
def test_worksheet_form_b(client):
    params = {"lesson": "2.4", "count": 6, "seed": 5, "level": "A"}
    a = client.get("/api/v1/papers/worksheet", params).json()
    b = client.get("/api/v1/papers/worksheet", {**params, "form": "B"}).json()
    assert shape(a) == shape(b) and len(b["questions"]) == 6
    assert all(p["level"] == "A" for q in b["questions"] for p in q["parts"])
    assert not (fingerprints(a) & fingerprints(b))


@pytest.mark.django_db
def test_answer_index_points_at_the_correct_option(client):
    paper = client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": 3}).json()
    labels = "ABCD"
    for question in paper["questions"]:
        for part in question["parts"]:
            if not part["options"]:
                assert part["answer_index"] == -1
            elif part["option_graphs"]:
                assert part["answer"] == f"الخيار ({labels[part['answer_index']]})"
            else:
                assert part["options"][part["answer_index"]] == part["answer"]


@pytest.mark.django_db
def test_unknown_form_rejected(client):
    assert client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": 3, "form": "C"}).status_code == 422
