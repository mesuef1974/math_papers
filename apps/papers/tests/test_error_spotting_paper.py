"""عرض «اكتشف الخطأ» (M3.3): ورقة العمل باختيار المعلم، والمفتاح وWord، ولا يدخل الاختبارات."""

import io
import json
import random

import pytest
from docx import Document
from docx.oxml.ns import qn
from lxml import etree

from apps.curriculum.courses import GRADE10_SLUG
from apps.papers import services
from apps.papers.domain.generators import ERROR_KINDS, ERROR_SPOTTING
from apps.papers.word.builder import build_docx, split_math
from apps.papers.word.omml import split_array, to_omml

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("loaded_courses")]

PROFILE = {
    "school": "مدرسة",
    "teacher_name": "",
    "subject": "الرياضيات",
    "grade": "",
    "exam_minutes": 60,
    "exam_instructions": "",
    "worksheet_instructions": "",
}
QUERY = {"lesson": "1.1", "count": 3, "seed": 5, "course": GRADE10_SLUG}


def get_worksheet(client, **extra):
    response = client.get("/api/v1/papers/worksheet", {**QUERY, **extra})
    assert response.status_code == 200, response.content
    return response.json()


def post(client, path, body):
    return client.post(path, json.dumps(body), content_type="application/json")


def parts(paper):
    return [part for question in paper["questions"] for part in question["parts"]]


def document_text(data: bytes) -> str:
    body = Document(io.BytesIO(data)).element.body
    return "\n".join("".join(t.text or "" for t in p.iter(qn("w:t"))) for p in body.iter(qn("w:p")))


def recipe(paper, **extra):
    return {
        "kind": paper["kind"],
        "lesson_code": "1.1",
        "seed": paper["seed"],
        "course": GRADE10_SLUG,
        **extra,
    }


def test_teacher_choice_appends_one_question_and_keeps_seeded_problems(client):
    plain, spotted = get_worksheet(client), get_worksheet(client, spotting="true")
    assert spotted["questions"][:3] == plain["questions"]
    assert not any(part["spotting"] for part in parts(plain))
    part = parts(spotted)[-1]
    spotting = part["spotting"]
    assert len(spotted["questions"]) == 4 and part["level"] == "R" and part["marking"] == []
    assert 1 <= spotting["wrong_step"] <= len(spotting["steps"])
    assert spotting["diagnosis"] == ERROR_KINDS[spotting["error_kind"]]
    assert part["source_example"]
    assert get_worksheet(client, spotting="true") == spotted


def test_form_b_keeps_the_formula_with_new_numbers(client):
    a = parts(get_worksheet(client, spotting="true"))[-1]
    b = parts(get_worksheet(client, spotting="true", form="B"))[-1]
    assert b["spotting"] and b["variant"] == a["variant"] and b["fingerprint"] != a["fingerprint"]


def test_lesson_without_a_variant_is_refused(client):
    response = client.get(
        "/api/v1/papers/worksheet", {"lesson": "1.1", "count": 2, "seed": 1, "spotting": "true"}
    )
    assert response.status_code == 404 and "اكتشف الخطأ" in response.json()["detail"]


def test_replacement_stays_error_spotting(client):
    part = parts(get_worksheet(client, spotting="true"))[-1]
    body = {
        "lesson": part["lesson"],
        "slot": part["slot"],
        "exclude": [part["fingerprint"]],
        "seed": 9,
        "course": GRADE10_SLUG,
        "spotting": True,
    }
    response = post(client, "/api/v1/papers/replace-part", body)
    assert response.status_code == 200, response.content
    new = response.json()
    assert new["spotting"] and new["fingerprint"] != part["fingerprint"]


def test_saving_derives_the_diagnosis_and_old_snapshots_still_open(client):
    paper = get_worksheet(client, spotting="true")
    expected = parts(paper)[-1]["spotting"]["diagnosis"]
    parts(paper)[-1]["spotting"]["diagnosis"] = "من العميل"
    parts(paper)[-1]["level"] = "K"
    saved = post(client, "/api/v1/saved", {"paper": paper, "recipe": recipe(paper, spotting=True)}).json()
    last = parts(saved["paper"])[-1]
    assert last["spotting"]["diagnosis"] == expected and last["level"] == "R"

    old = get_worksheet(client, seed=8)
    for part in parts(old):
        del part["spotting"]
    response = post(client, "/api/v1/saved", {"paper": old, "recipe": recipe(old)})
    assert response.status_code == 201, response.content
    opened = client.get(f"/api/v1/saved/{response.json()['id']}").json()
    assert all(part["spotting"] is None for part in parts(opened["paper"]))


def test_no_exam_quiz_bundle_or_form_carries_error_spotting(client):
    slugs = [row["slug"] for row in client.get("/api/v1/blueprints").json()]
    papers = [services.build_exam(slug, 3, form) for slug in slugs for form in services.FORMS]
    for slug in slugs:
        papers += [services.build_bundle_item(slug, row["lesson"], 3) for row in services.bundle_plan(slug)]
    papers += [
        services.build_quiz([lesson], 3, form, GRADE10_SLUG) for lesson in ("1.1", "2.6") for form in "AB"
    ]
    assert slugs and not any(part.get("spotting") for paper in papers for part in parts(paper))


@pytest.mark.parametrize("kind", ["exam", "quiz"])
def test_client_cannot_put_error_spotting_into_a_test(client, kind):
    paper = {**get_worksheet(client, spotting="true"), "kind": kind}
    for path in ("/api/v1/pdf", "/api/v1/docx"):
        assert post(client, path, {"papers": [paper], "profile": PROFILE}).status_code == 422
    assert post(client, "/api/v1/saved", {"paper": paper, "recipe": recipe(paper)}).status_code == 422


@pytest.mark.parametrize("template", ["awraq", "school"])
def test_word_shows_numbered_steps_and_the_key_names_step_kind_and_dok(client, template):
    paper = get_worksheet(client, spotting="true")
    spotting = parts(paper)[-1]["spotting"]
    payload = {"papers": [paper], "profile": PROFILE, "template": template}
    sheet = document_text(build_docx(payload))
    for number in range(1, len(spotting["steps"]) + 1):
        assert f"‏{number}‏-" in sheet
    assert "نوع الخطأ:" not in sheet and "الخطوة الصحيحة:" not in sheet

    key_options = {"key_only": True} if template == "school" else {"show_key": True}
    key = document_text(build_docx({**payload, **key_options}))
    for expected in (
        f"الخطوة الخاطئة: {spotting['wrong_step']}",
        f"نوع الخطأ: {ERROR_KINDS[spotting['error_kind']]}",
        "الخطوة الصحيحة: ",
        "الجواب: ",
        "DOK 3",
    ):
        assert expected in key, expected


def test_every_error_spotting_formula_converts_to_word_math():
    for fns in ERROR_SPOTTING.values():
        for fn in fns:
            for seed in range(8):
                item = fn(random.Random(seed))
                for text in (item.stem, item.answer, item.correct_step, *item.steps):
                    for is_math, _, value in split_math(text):
                        if is_math and not split_array(value):
                            root = etree.fromstring(to_omml(value))
                            assert "\\" not in "".join(root.itertext()), value
