"""جدول المواصفات في العقد والمحمِّل: مخطط صارم، ونطاق الاختبار، وتحميل idempotent، وعزل بين المقررات."""

import hashlib
import json
from collections import Counter

import pytest
from pydantic import ValidationError

from apps.curriculum.courses import GRADE10_SLUG, GRADE12_SLUG
from apps.curriculum.models import Blueprint, BlueprintItem, Course
from apps.knowledge import models as km
from apps.knowledge.domain.contract import BlueprintData, CourseKnowledge, read_source
from apps.knowledge.services import BlueprintOwnerError, load_all, load_contract, load_course
from apps.papers import services as papers
from apps.planning.domain.semester_plan import load_term_plan

pytestmark = pytest.mark.django_db

FINAL = "g10-s1-2026-27-final"
G12_FORECAST = "g12-sci-s1-2026-27-forecast"
ENRICHMENT = {"1.4", "2.4", "3.1", "3.2"}
# مجموعات جدول الوزارة: الدروس، ثم (عدد الموضوعي، درجته، عدد المقالي، درجته)
GROUPS = {
    ("1.1", "1.2", "1.3"): (2, 4, 1, 5),
    ("2.1", "2.2", "2.3", "2.5", "2.6"): (4, 8, 3, 11),
    ("2.7", "2.8", "2.9", "2.10"): (2, 4, 3, 9),
    ("3.3", "3.4", "3.5"): (2, 4, 1, 5),
}


def grade10() -> dict:
    return json.loads(json.dumps(read_source(GRADE10_SLUG).model_dump()))


def final(data: dict) -> dict:
    (blueprint,) = data["blueprints"]
    return blueprint


# --- العقد ---


def test_grade10_blueprint_matches_the_ministry_table():
    blueprint = read_source(GRADE10_SLUG).blueprints[0]
    assert (blueprint.slug, blueprint.total_marks, blueprint.is_forecast) == (FINAL, 50, False)
    assert (blueprint.academic_year, blueprint.semester) == ("2026-2027", 1)
    assert len({item.question_number for item in blueprint.items}) == 18
    by_level: Counter = Counter()
    for item in blueprint.items:
        by_level[item.level] += item.marks
    assert by_level == {"K": 25, "A": 20, "R": 5}

    mcq = [item for item in blueprint.items if item.kind == "mcq"]
    essay = [item for item in blueprint.items if item.kind == "essay"]
    assert [item.question_number for item in mcq] == list(range(1, 11))
    assert {item.marks for item in mcq} == {2} and sum(item.marks for item in essay) == 30
    question_marks: Counter = Counter()
    for item in essay:
        question_marks[item.question_number] += item.marks
    assert sorted(question_marks) == list(range(11, 19))
    assert all(3 <= marks <= 5 for marks in question_marks.values())

    for lessons, (mcq_count, mcq_marks, essay_count, essay_marks) in GROUPS.items():
        # السؤال للمجموعة التي منها فرعه الأول، كما يعدّه الجدول
        first = [item for item in blueprint.items if item.position == 1 and item.lesson in lessons]
        inside = [item for item in blueprint.items if item.lesson in lessons]
        assert sum(item.kind == "mcq" for item in first) == mcq_count, lessons
        assert sum(item.kind == "essay" for item in first) == essay_count, lessons
        assert sum(item.marks for item in inside if item.kind == "mcq") == mcq_marks, lessons
        assert sum(item.marks for item in inside if item.kind == "essay") == essay_marks, lessons
    covered = {item.lesson for item in blueprint.items}
    assert covered == {code for group in GROUPS for code in group}


def test_exam_scope_has_one_source_and_the_manifest_follows_it():
    plan = load_term_plan()
    knowledge = read_source(GRADE10_SLUG)
    assert (
        {ref.code for ref in knowledge.lessons if not ref.examinable} == plan.enrichment_lessons == ENRICHMENT
    )
    assert plan.enrichment_examples["3.3"] == (1, 2)
    assert not {item.lesson for item in knowledge.blueprints[0].items} & plan.enrichment_lessons


@pytest.mark.parametrize("lesson", sorted(ENRICHMENT))
def test_contract_rejects_an_item_for_an_enrichment_lesson(lesson):
    data = grade10()
    final(data)["items"][0]["lesson"] = lesson
    with pytest.raises(ValidationError, match="غير اختباري"):
        CourseKnowledge(**data)


def test_contract_rejects_bad_blueprints():
    data = grade10()
    final(data)["items"][0]["lesson"] = "9.9"
    with pytest.raises(ValidationError, match="خارج المقرر"):
        CourseKnowledge(**data)

    data = grade10()
    final(data)["items"][1].update(question_number=1, position=1)
    with pytest.raises(ValidationError, match="خانة مكررة"):
        CourseKnowledge(**data)

    data = grade10()
    final(data)["items"][0]["marks"] = 3
    with pytest.raises(ValidationError, match="مجموعها 51 والمعلن 50"):
        CourseKnowledge(**data)

    data = grade10()
    data["blueprints"].append(final(data))
    with pytest.raises(ValidationError, match="معرّف جدول مواصفات مكرر"):
        CourseKnowledge(**data)

    base = final(grade10())
    for change in (
        {"note": "نص حر"},  # لا حقل نصي حر
        {"slug": "Final 2026"},
        {"academic_year": "2026"},
        {"items": []},
        {"total_marks": 0},
    ):
        with pytest.raises(ValidationError):
            BlueprintData(**{**base, **change})
    for change in ({"kind": "oral"}, {"level": "X"}, {"marks": 0}, {"marks": 2.5}, {"stem": "نص سؤال"}):
        with pytest.raises(ValidationError):
            BlueprintData(**{**base, "items": [{**base["items"][0], **change}]})


def test_course_without_blueprints_keeps_its_content_hash():
    """الحقل الجديد خارج تجزئة مقرر بلا جداول: الثاني عشر لا يصدر له إصدار ولا يتغير فحص صحته."""
    knowledge = read_source(GRADE12_SLUG)
    assert knowledge.blueprints == []
    payload = knowledge.model_dump()
    del payload["blueprints"]
    before = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert knowledge.content_hash() == hashlib.sha256(before.encode("utf-8")).hexdigest()

    grade10 = read_source(GRADE10_SLUG)
    edited = grade10.model_copy(deep=True)
    edited.blueprints[0].items[0].needs_graph = True
    assert edited.content_hash() != grade10.content_hash()


# --- المحمِّل ---


def test_loader_writes_the_blueprint_and_second_load_changes_nothing():
    report = load_course(GRADE10_SLUG)
    assert report.changed["blueprints"] == 1 and report.changed["blueprint_items"] == 19
    blueprint = Blueprint.objects.get(slug=FINAL)
    assert blueprint.course.slug == GRADE10_SLUG and not blueprint.is_forecast
    assert (blueprint.total_marks, blueprint.academic_year, blueprint.semester) == (50, "2026-2027", 1)
    items = list(blueprint.items.select_related("lesson__course"))
    assert len(items) == 19 and sum(item.marks for item in items) == 50
    assert {item.lesson.course.slug for item in items} == {GRADE10_SLUG}
    assert all(item.lesson.examinable for item in items)
    assert not blueprint.items.filter(lesson__code__in=ENRICHMENT).exists()
    eleven = [(i.position, i.lesson.code, i.marks) for i in items if i.question_number == 11]
    assert eleven == [(1, "1.3", 3), (2, "1.2", 2)]

    assert load_course(GRADE10_SLUG).total == 0
    assert km.KnowledgeRelease.objects.filter(course__slug=GRADE10_SLUG).count() == 1


def test_enrichment_lessons_are_loaded_as_not_examinable():
    load_course(GRADE10_SLUG)
    course = Course.objects.get(slug=GRADE10_SLUG)
    assert set(course.lessons.filter(examinable=False).values_list("code", flat=True)) == ENRICHMENT


def test_loader_repairs_edited_missing_and_extra_slots():
    load_course(GRADE10_SLUG)
    blueprint = Blueprint.objects.get(slug=FINAL)
    kept = blueprint.items.get(question_number=18).pk
    blueprint.items.filter(question_number=1).update(marks=9, level="R")
    blueprint.items.filter(question_number=2).delete()
    BlueprintItem.objects.create(
        blueprint=blueprint,
        lesson=blueprint.items.first().lesson,
        question_number=19,
        position=1,
        kind="essay",
        marks=4,
    )
    Blueprint.objects.filter(pk=blueprint.pk).update(title="عنوان آخر", is_forecast=True)

    report = load_course(GRADE10_SLUG)
    assert report.changed["blueprint_items"] == 3 and report.changed["blueprints"] == 1
    assert km.KnowledgeRelease.objects.filter(course__slug=GRADE10_SLUG).count() == 1  # المحتوى لم يتغير
    blueprint.refresh_from_db()
    assert not blueprint.is_forecast and blueprint.title == read_source(GRADE10_SLUG).blueprints[0].title
    assert blueprint.items.count() == 19 and not blueprint.items.filter(question_number=19).exists()
    assert sum(blueprint.items.values_list("marks", flat=True)) == 50
    assert blueprint.items.get(question_number=18).pk == kept  # الخانة السليمة لا تُعاد كتابتها
    assert load_course(GRADE10_SLUG).total == 0


def test_removing_an_item_from_the_source_removes_its_slot():
    knowledge = read_source(GRADE10_SLUG)
    load_contract(knowledge)
    edited = knowledge.model_copy(deep=True)
    dropped = edited.blueprints[0].items.pop()
    edited.blueprints[0].total_marks -= dropped.marks
    report = load_contract(edited)
    assert report.changed["blueprint_items"] == 1 and report.changed["releases"] == 1
    assert Blueprint.objects.get(slug=FINAL).items.count() == 18


def test_loader_refuses_a_slug_owned_by_another_course():
    load_all()
    knowledge = read_source(GRADE10_SLUG)
    stolen = knowledge.model_copy(deep=True)
    stolen.blueprints[0].slug = G12_FORECAST
    before = list(BlueprintItem.objects.filter(blueprint__slug=G12_FORECAST).values_list("pk", "marks"))
    with pytest.raises(BlueprintOwnerError, match="يملكه مقرر آخر"):
        load_contract(stolen)
    seeded = Blueprint.objects.get(slug=G12_FORECAST)
    assert seeded.course.slug == GRADE12_SLUG and seeded.total_marks == 40
    assert list(seeded.items.values_list("pk", "marks")) == before
    # الرفض يُبطل المعاملة كلها: لا إصدار بتجزئة العقد المرفوض
    assert not km.KnowledgeRelease.objects.filter(content_hash=stolen.content_hash()).exists()


def test_grade12_seeded_blueprint_and_release_are_untouched():
    seeded = Blueprint.objects.get(slug=G12_FORECAST)
    before = list(seeded.items.values_list("pk", "lesson_id", "kind", "marks", "level", "needs_graph"))
    load_all()
    assert load_course(GRADE12_SLUG).changed["blueprints"] == 0
    seeded.refresh_from_db()
    assert seeded.is_forecast and seeded.course.slug == GRADE12_SLUG
    assert (
        list(seeded.items.values_list("pk", "lesson_id", "kind", "marks", "level", "needs_graph")) == before
    )
    assert Blueprint.objects.count() == 2


def test_health_stays_ok_for_both_courses(client):
    load_all()
    assert client.get("/health/").json()["knowledge"] == {GRADE12_SLUG: "ok", GRADE10_SLUG: "ok"}


# --- العرض للتوليد: جدول بلا مولّدات لا يُعرض ولا يُسقط المسار ---


def test_complete_grade10_blueprint_is_offered_and_builds_a_full_exam():
    """بعد المرحلة 5 كل خانات جدول العاشر لها مولّدات: يُعرض ويولَّد اختبارًا كاملًا بـ18 سؤالًا و50 درجة."""
    load_all()
    assert {blueprint.slug for blueprint in papers.ready_blueprints()} == {G12_FORECAST, FINAL}
    for seed in range(1, 6):
        paper = papers.build_exam(FINAL, seed=seed)
        assert [q["number"] for q in paper["questions"]] == list(range(1, 19))
        assert sum(q["marks"] for q in paper["questions"]) == paper["total_marks"] == 50
        assert paper["level_marks"] == {"K": 25, "A": 20, "R": 5}


def test_blueprint_without_generators_is_loaded_but_not_offered(monkeypatch):
    """يُحجب درس 3.5 مؤقتًا: جدول العاشر كامل المولّدات منذ المرحلة 5، فيُحاكى غيابها."""
    from apps.papers.domain.generators import REGISTRY

    load_all()
    monkeypatch.delitem(REGISTRY, (GRADE10_SLUG, "3.5"))
    assert [blueprint.slug for blueprint in papers.ready_blueprints()] == [G12_FORECAST]
    assert not papers.blueprint_ready(Blueprint.objects.get(slug=FINAL))
    with pytest.raises(papers.BlueprintNotReadyError):
        papers.build_exam(FINAL, seed=1)
