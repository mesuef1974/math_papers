import json

import pytest

from apps.core.models import AuditLog
from apps.papers import services
from apps.papers.models import SavedPaper

SLUG = "g12-sci-s1-2026-27-forecast"


def post(client, path, body):
    return client.post(path, json.dumps(body), content_type="application/json")


def patch(client, path, body):
    return client.patch(path, json.dumps(body), content_type="application/json")


def worksheet(client, seed=3, count=5):
    return client.get("/api/v1/papers/worksheet", {"lesson": "1.2", "count": count, "seed": seed}).json()


def recipe_for(paper, replacements=()):
    return {
        "kind": paper["kind"],
        "blueprint": paper["blueprint"],
        "lesson_code": paper["lesson_code"],
        "count": len(paper["questions"]) if paper["kind"] == "worksheet" else 0,
        "level": paper["level"],
        "seed": paper["seed"],
        "replacements": list(replacements),
    }


def fingerprints(paper):
    return [part["fingerprint"] for q in paper["questions"] for part in q["parts"]]


# ---------- الاستبدال ----------


@pytest.mark.django_db
def test_replacement_keeps_slot_and_avoids_everything_in_the_paper(client):
    exam = client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": 7}).json()
    part = exam["questions"][0]["parts"][0]
    body = {
        "lesson": part["lesson"],
        "label": part["label"],
        "marks": part["marks"],
        "slot": part["slot"],
        "exclude": fingerprints(exam),
        "seed": 99,
    }
    res = post(client, "/api/v1/papers/replace-part", body)
    assert res.status_code == 200, res.content
    new = res.json()
    assert new["slot"] == part["slot"] and new["lesson"] == part["lesson"] and new["marks"] == part["marks"]
    assert new["fingerprint"] not in fingerprints(exam)
    assert new["seed"] == 99 and len(new["options"]) == 4
    if part["slot"]["level"]:
        assert new["level"] == part["slot"]["level"]
    again = post(client, "/api/v1/papers/replace-part", body).json()
    assert again == new  # البذرة تعيد البديل نفسه


@pytest.mark.django_db
def test_replacement_rejects_unknown_lesson(client):
    body = {"lesson": "9.9", "slot": {"kind": "essay", "level": "", "needs_graph": False}}
    assert post(client, "/api/v1/papers/replace-part", body).status_code == 404


# ---------- الحفظ ----------


@pytest.mark.django_db
def test_save_roundtrip_is_idempotent_and_audited(client):
    paper = worksheet(client)
    body = {"title": "  ورقة الأسبوع 3 ", "paper": paper, "recipe": recipe_for(paper)}
    first = post(client, "/api/v1/saved", body)
    assert first.status_code == 201, first.content
    saved = first.json()
    assert (
        saved["title"] == "ورقة الأسبوع 3" and saved["question_count"] == 5 and saved["lesson_code"] == "1.2"
    )
    second = post(client, "/api/v1/saved", body)
    assert second.status_code == 200 and second.json()["id"] == saved["id"]
    assert SavedPaper.objects.count() == 1
    assert AuditLog.objects.filter(action="saved_paper.create").count() == 1

    detail = client.get(f"/api/v1/saved/{saved['id']}").json()
    assert detail["paper"] == paper and detail["recipe"]["seed"] == paper["seed"]
    rows = client.get("/api/v1/saved").json()
    assert [row["id"] for row in rows] == [saved["id"]] and "paper" not in rows[0]
    # الوصفة بلا مقرر تُحفظ على المقرر الحالي، وبصمتها كما كانت قبل عمود المقرر
    assert saved["course"] == rows[0]["course"] == "g12-sci-s1"
    assert "course" not in SavedPaper.objects.get().recipe


@pytest.mark.django_db
def test_course_is_required_and_the_guard_migration_is_idempotent(client):
    import importlib

    from django.apps import apps
    from django.db import IntegrityError, transaction

    paper = worksheet(client)
    pk = post(client, "/api/v1/saved", {"paper": paper, "recipe": recipe_for(paper)}).json()["id"]
    guard = importlib.import_module("apps.papers.migrations.0006_saved_paper_course_guard")
    guard.forwards(apps, None)
    guard.forwards(apps, None)
    assert SavedPaper.objects.get(pk=pk).course.slug == "g12-sci-s1"
    assert client.get("/api/v1/saved").json()[0]["course"] == "g12-sci-s1"
    with pytest.raises(IntegrityError), transaction.atomic():
        SavedPaper.objects.filter(pk=pk).update(course=None)


@pytest.mark.django_db
def test_unknown_recipe_course_is_rejected_not_saved_without_course(client):
    paper = worksheet(client)
    res = post(client, "/api/v1/saved", {"paper": paper, "recipe": {**recipe_for(paper), "course": "nope"}})
    assert res.status_code == 422
    assert not SavedPaper.objects.exists()


@pytest.mark.django_db
def test_title_defaults_to_paper_title_and_kind_must_match(client):
    paper = worksheet(client, seed=4)
    res = post(client, "/api/v1/saved", {"paper": paper, "recipe": recipe_for(paper)})
    assert res.status_code == 201 and res.json()["title"] == paper["title"]
    bad = post(client, "/api/v1/saved", {"paper": paper, "recipe": {**recipe_for(paper), "kind": "exam"}})
    assert bad.status_code == 422


@pytest.mark.django_db
def test_saved_papers_are_owner_scoped(client, django_user_model):
    paper = worksheet(client)
    pk = post(client, "/api/v1/saved", {"paper": paper, "recipe": recipe_for(paper)}).json()["id"]
    other = django_user_model.objects.create_superuser(username="other", password="Rasm-Bayani-2026")
    client.force_login(other)
    assert client.get("/api/v1/saved").json() == []
    assert client.get(f"/api/v1/saved/{pk}").status_code == 404
    assert client.delete(f"/api/v1/saved/{pk}").status_code == 204  # لا يكشف ولا يحذف
    assert SavedPaper.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_rename_update_after_replacement_and_delete(client):
    paper = worksheet(client)
    pk = post(client, "/api/v1/saved", {"paper": paper, "recipe": recipe_for(paper)}).json()["id"]

    renamed = patch(client, f"/api/v1/saved/{pk}", {"title": "اسم جديد"})
    assert renamed.status_code == 200 and renamed.json()["title"] == "اسم جديد"
    assert patch(client, f"/api/v1/saved/{pk}", {"title": "اسم جديد"}).status_code == 200
    assert AuditLog.objects.filter(action="saved_paper.update").count() == 1  # التكرار لا يسجَّل

    part = paper["questions"][0]["parts"][0]
    new = post(
        client,
        "/api/v1/papers/replace-part",
        {"lesson": part["lesson"], "slot": part["slot"], "exclude": fingerprints(paper), "seed": 5},
    ).json()
    seed = new.pop("seed")
    edited = {**paper, "questions": [{**paper["questions"][0], "parts": [new]}, *paper["questions"][1:]]}
    recipe = recipe_for(
        paper, [{"question": 1, "label": "", "seed": seed, "fingerprint": new["fingerprint"]}]
    )
    res = patch(client, f"/api/v1/saved/{pk}", {"paper": edited, "recipe": recipe})
    assert res.status_code == 200, res.content
    assert res.json()["replacement_count"] == 1
    assert (
        client.get(f"/api/v1/saved/{pk}").json()["paper"]["questions"][0]["parts"][0]["stem"] == new["stem"]
    )
    assert patch(client, f"/api/v1/saved/{pk}", {"paper": edited}).status_code == 422

    assert client.delete(f"/api/v1/saved/{pk}").status_code == 204
    assert client.get(f"/api/v1/saved/{pk}").status_code == 404
    assert client.delete(f"/api/v1/saved/{pk}").status_code == 204
    assert AuditLog.objects.filter(action="saved_paper.delete").count() == 1


@pytest.mark.django_db
def test_update_cannot_collide_with_another_saved_paper(client):
    a = worksheet(client, seed=1)
    b = worksheet(client, seed=2)
    post(client, "/api/v1/saved", {"paper": a, "recipe": recipe_for(a)})
    pk_b = post(client, "/api/v1/saved", {"paper": b, "recipe": recipe_for(b)}).json()["id"]
    res = patch(client, f"/api/v1/saved/{pk_b}", {"paper": a, "recipe": recipe_for(a)})
    assert res.status_code == 409


@pytest.mark.django_db
def test_limit_per_teacher(client, monkeypatch):
    monkeypatch.setattr(services, "MAX_SAVED_PER_USER", 1)
    a = worksheet(client, seed=1)
    b = worksheet(client, seed=2)
    assert post(client, "/api/v1/saved", {"paper": a, "recipe": recipe_for(a)}).status_code == 201
    assert post(client, "/api/v1/saved", {"paper": a, "recipe": recipe_for(a)}).status_code == 200
    assert post(client, "/api/v1/saved", {"paper": b, "recipe": recipe_for(b)}).status_code == 409
