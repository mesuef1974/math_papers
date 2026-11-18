"""المرحلة 2: العقد القانوني والمحمِّل الواحد وإصدارات المعرفة وفحص الصحة."""

import json
import shutil

import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings
from pydantic import ValidationError

from apps.curriculum.courses import GRADE10_SLUG, GRADE12_SLUG
from apps.curriculum.models import Course, Lesson
from apps.knowledge import models as km
from apps.knowledge.domain import contract
from apps.knowledge.domain.contract import CourseKnowledge, read_source, source_hash, source_slugs
from apps.knowledge.selectors import course_index, course_index_from_tables, knowledge_state
from apps.knowledge.services import load_all, load_contract, load_course

pytestmark = pytest.mark.django_db


def test_both_sources_validate_against_one_contract():
    assert source_slugs() == [GRADE10_SLUG, GRADE12_SLUG]  # كل مجلد فيه course.json، بترتيب ثابت
    for slug in source_slugs():
        knowledge = read_source(slug)
        assert isinstance(knowledge, CourseKnowledge) and knowledge.schema_version == 1
        assert knowledge.course.slug == slug and len(knowledge.lessons) >= 19
        assert {p.lesson for p in knowledge.profiles} <= {lesson.code for lesson in knowledge.lessons}


def test_content_hash_is_stable_and_sensitive():
    first = read_source(GRADE12_SLUG)
    assert first.content_hash() == read_source(GRADE12_SLUG).content_hash()
    assert read_source(GRADE10_SLUG).content_hash() != first.content_hash()
    changed = first.model_copy(deep=True)
    changed.profiles[0].objective = changed.profiles[0].objective + " "
    assert changed.content_hash() != first.content_hash()


def test_contract_rejects_bad_shapes():
    base = read_source(GRADE10_SLUG).model_dump()
    with pytest.raises(ValidationError, match="مكرر"):
        CourseKnowledge(**{**base, "lessons": base["lessons"] + base["lessons"][:1]})
    with pytest.raises(ValidationError, match="غير مذكور"):
        CourseKnowledge(**{**base, "lessons": base["lessons"][1:]})
    bad = json.loads(json.dumps(base))
    bad["profiles"][0]["standards"] = ["99.9.9"]
    with pytest.raises(ValidationError, match="رمز معيار"):
        CourseKnowledge(**bad)
    bad = json.loads(json.dumps(base))
    bad["profiles"][0]["task_basic"] = "abc"
    with pytest.raises(ValidationError, match="مدى"):
        CourseKnowledge(**bad)
    with pytest.raises(ValidationError):
        CourseKnowledge(**{**base, "schema_version": 2})


def test_second_load_changes_nothing_for_every_course():
    first = load_all()
    assert all(report.total > 0 for report in first.values())
    second = load_all()
    assert {slug: report.total for slug, report in second.items()} == {GRADE12_SLUG: 0, GRADE10_SLUG: 0}
    assert km.KnowledgeRelease.objects.count() == 2


def test_lesson_36_is_loaded_and_both_books_share_the_same_tables():
    load_all()
    assert Lesson.objects.get(course__slug=GRADE12_SLUG, code="3.6").profile.templates.count() == 15
    g10 = km.LessonProfile.objects.filter(lesson__course__slug=GRADE10_SLUG)
    g12 = km.LessonProfile.objects.filter(lesson__course__slug=GRADE12_SLUG)
    assert (g10.count(), g12.count()) == (19, 19)
    assert set(g10.values_list("source", flat=True)) == {"extracted"}
    assert set(g12.values_list("source", flat=True)) == {"authored"}
    # رمز واحد في مقررين: درسان منفصلان بملفين منفصلين
    one_one = km.LessonProfile.objects.filter(lesson__code="1.1")
    assert one_one.count() == 2 and len({p.lesson_id for p in one_one}) == 2


def test_loading_grade10_leaves_grade12_untouched():
    load_course(GRADE12_SLUG)
    before = km.KnowledgeRelease.objects.get(course__slug=GRADE12_SLUG)
    items = km.LessonItem.objects.count()
    load_course(GRADE10_SLUG)
    assert km.LessonItem.objects.count() == items
    assert km.KnowledgeRelease.objects.filter(course__slug=GRADE12_SLUG).get() == before


def test_grade10_enters_with_no_guide_text():
    load_course(GRADE10_SLUG)
    for profile in km.LessonProfile.objects.filter(lesson__course__slug=GRADE10_SLUG):
        assert not (profile.objective or profile.rationale or profile.motivation or profile.title_en)
        assert not profile.items.exists() and not profile.terms.exists() and not profile.templates.exists()
        assert all(o.text == "" for o in profile.objectives.all())
        assert all(e.skill == "" for e in profile.examples.all())
        assert profile.lesson.title and profile.lesson.title != f"الدرس {profile.lesson.code}"  # عنوان الكتاب لا العنوان المؤقت
    assert not km.UnitProfile.objects.filter(course__slug=GRADE10_SLUG).exists()
    assert not km.PedagogyNote.objects.filter(course__slug=GRADE10_SLUG).exists()


def test_grade10_index_is_derivable_from_the_tables():
    load_course(GRADE10_SLUG)
    assert course_index_from_tables(GRADE10_SLUG).model_dump() == course_index(GRADE10_SLUG).model_dump()


def test_loader_repairs_drift_in_new_tables():
    load_course(GRADE10_SLUG)
    profile = km.LessonProfile.objects.get(lesson__course__slug=GRADE10_SLUG, lesson__code="1.4")
    profile.exercise_groups.all().delete()
    profile.objectives.first().delete()
    report = load_course(GRADE10_SLUG)
    assert report.changed["exercise_groups"] == 1 and report.changed["objectives"] == 1
    assert km.KnowledgeRelease.objects.filter(course__slug=GRADE10_SLUG).count() == 1  # المحتوى لم يتغير


def test_release_recorded_only_when_hash_changes():
    knowledge = read_source(GRADE10_SLUG)
    load_contract(knowledge)
    load_contract(knowledge)
    edited = knowledge.model_copy(deep=True)
    edited.profiles[0].exercises_total = (edited.profiles[0].exercises_total or 0) + 1
    report = load_contract(edited)
    assert report.changed["releases"] == 1 and report.changed["profiles"] == 1
    releases = list(km.KnowledgeRelease.objects.filter(course__slug=GRADE10_SLUG))
    assert len(releases) == 2 and releases[0].content_hash == edited.content_hash()
    assert releases[0].schema_version == 1 and releases[0].report["profiles"] == 1


def test_course_loading_does_not_flip_the_current_course():
    load_all()
    assert Course.objects.get(is_current=True).slug == GRADE12_SLUG
    assert not Course.objects.get(slug=GRADE10_SLUG).is_current


def test_command_loads_one_or_all_and_rejects_bad_input(capsys):
    call_command("load_course", GRADE10_SLUG)
    call_command("load_course", "--all")
    out = capsys.readouterr().out
    assert f"{GRADE10_SLUG}: تغيّر" in out and "لا شيء" in out
    with pytest.raises(CommandError, match="لا مصدر"):
        call_command("load_course", "nope")
    with pytest.raises(CommandError, match="--all"):
        call_command("load_course")
    with pytest.raises(CommandError, match="--all"):
        call_command("load_course", GRADE10_SLUG, "--all")


# --- /health/ ---


def _copied_courses(tmp_path, monkeypatch):
    """نسخة من مجلدات المقررات يُعدَّل فيها بأمان؛ المصادر تُكتشف من الجذر وقت النداء."""
    root = tmp_path / "courses"
    shutil.copytree(contract.COURSES_DIR, root)
    monkeypatch.setattr(contract, "COURSES_DIR", root)
    return root


def test_health_reports_unloaded_then_ok(client):
    body = client.get("/health/").json()
    assert body["status"] == "degraded" and set(body["knowledge"].values()) == {"unloaded"}
    assert client.get("/health/").status_code == 200  # الصرامة مطفأة افتراضيًا
    load_all()
    res = client.get("/health/")
    assert res.status_code == 200 and res.json() == {
        "db": "ok",
        "status": "ok",
        "knowledge": {GRADE12_SLUG: "ok", GRADE10_SLUG: "ok"},
    }


@override_settings(KNOWLEDGE_HEALTH_STRICT=True)
def test_health_is_503_when_strict_and_not_loaded(client):
    assert client.get("/health/").status_code == 503
    load_all()
    assert client.get("/health/").status_code == 200


@override_settings(KNOWLEDGE_HEALTH_STRICT=True)
def test_health_turns_red_when_a_source_file_changes_without_loading(client, tmp_path, monkeypatch):
    copy = _copied_courses(tmp_path, monkeypatch) / GRADE10_SLUG / contract.INDEX
    load_all()
    assert client.get("/health/").status_code == 200

    data = json.loads(copy.read_text(encoding="utf-8"))
    data["lessons"][0]["exercises_total"] += 1
    copy.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    res = client.get("/health/")
    assert res.status_code == 503
    assert res.json()["knowledge"] == {GRADE12_SLUG: "ok", GRADE10_SLUG: "stale"}

    load_course(GRADE10_SLUG)  # التحميل يعيدها خضراء
    assert client.get("/health/").status_code == 200


def test_source_hash_tracks_file_changes_not_calls(tmp_path, monkeypatch):
    copy = _copied_courses(tmp_path, monkeypatch) / GRADE10_SLUG / contract.INDEX
    before = source_hash(GRADE10_SLUG)
    assert source_hash(GRADE10_SLUG) == before
    data = json.loads(copy.read_text(encoding="utf-8"))
    data["lessons"][0]["practices"] = []
    copy.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert source_hash(GRADE10_SLUG) != before


def test_knowledge_state_marks_old_schema_version_stale():
    load_all()
    km.KnowledgeRelease.objects.update(schema_version=0)
    assert set(knowledge_state().values()) == {"stale"}
