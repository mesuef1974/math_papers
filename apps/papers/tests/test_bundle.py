import pytest
from django.core.cache import cache

from apps.papers import services
from apps.papers.domain.generators import LEVEL_NAMES, lesson_levels

SLUG = "g12-sci-s1-2026-27-forecast"


@pytest.mark.django_db
def test_plan_counts_follow_blueprint_weight_and_levels_cover_every_available_level():
    plan = {row["lesson"]: row for row in services.bundle_plan(SLUG)}
    assert len(plan) == 18 and plan["3.4"]["count"] == 6  # 3.4 بلا درجات في الجدول لكنه في المنهج
    assert plan["3.3"]["count"] == 12 and plan["2.2"]["count"] == 6 and plan["1.2"]["count"] == 10
    for code, row in plan.items():
        assert sum(row["levels"].values()) == row["count"]
        assert set(row["levels"]) == set(lesson_levels(code))
        assert all(n >= 1 for n in row["levels"].values())
    # 2.3 في الجدول «عليا» فقط: الباقي بعد الحد الأدنى يذهب إلى R
    assert plan["2.3"]["levels"]["R"] == max(plan["2.3"]["levels"].values())


def test_split_keeps_minimum_and_distributes_remainder():
    assert services.split_levels(6, ["K", "A", "R"], {"A": 3}) == {"K": 1, "A": 4, "R": 1}
    assert services.split_levels(7, ["K", "A"], {}) == {"K": 4, "A": 3}


@pytest.mark.django_db
def test_bundle_item_is_ordered_easy_to_hard_and_deterministic(client):
    cache.clear()
    res = client.get("/api/v1/papers/bundle-item", {"blueprint": SLUG, "lesson": "3.3", "seed": 5})
    assert res.status_code == 200
    data = res.json()
    levels = [q["parts"][0]["level"] for q in data["questions"]]
    order = list(LEVEL_NAMES)
    assert levels == sorted(levels, key=order.index)
    assert len(levels) == 12 and data["level_counts"] and data["lesson_code"] == "3.3"
    again = client.get("/api/v1/papers/bundle-item", {"blueprint": SLUG, "lesson": "3.3", "seed": 5}).json()
    assert again == data
    other = client.get("/api/v1/papers/bundle-item", {"blueprint": SLUG, "lesson": "3.3", "seed": 6}).json()
    assert other["questions"] != data["questions"]


@pytest.mark.django_db
def test_bundle_item_rejects_unknown_lesson_or_blueprint(client):
    res = client.get("/api/v1/papers/bundle-item", {"blueprint": SLUG, "lesson": "3.6", "seed": 1})
    assert res.status_code == 404
    assert client.get("/api/v1/papers/bundle-plan", {"blueprint": "nope"}).status_code == 404


@pytest.mark.django_db
def test_whole_bundle_builds_for_every_lesson(client):
    plan = client.get("/api/v1/papers/bundle-plan", {"blueprint": SLUG}).json()
    for row in plan:
        res = client.get(
            "/api/v1/papers/bundle-item", {"blueprint": SLUG, "lesson": row["lesson"], "seed": 9}
        )
        assert res.status_code == 200, row
        assert len(res.json()["questions"]) == row["count"]
