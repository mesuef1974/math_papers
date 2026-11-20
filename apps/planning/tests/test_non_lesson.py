"""حصص غير الدروس (المرحلة 6 الجزء ب من docs/lesson_prep_plan.md، قرار المالك 2026-11-20): لكل حصة من الـ15 تحضير بمراحل
مجموعها 45 دقيقة ونطاق دروس مشتق من الخطة وورقة مولَّدة لأنواعها، ويُنزَّل بنموذج الوزارة نفسه."""

import re

import pytest

from apps.curriculum.courses import GRADE10_SLUG
from apps.planning import selectors
from apps.planning.domain.non_lesson import (
    KINDS,
    NonLessonPrep,
    Row,
    check_non_lesson,
    chunk,
    scope_lessons,
)
from apps.planning.domain.plan_periods import plan_periods
from apps.planning.domain.semester_plan import PlanEntry, PlanWeek, TermPlan

from .test_prep_api import TOKEN, document_text

API = "/api/v1/preps"


def test_chunk_splits_in_order_with_extra_first():
    items = ["a", "b", "c", "d", "e"]
    assert [chunk(items, 2, k) for k in (1, 2)] == [("a", "b", "c"), ("d", "e")]
    assert chunk(items, 1, 1) == tuple(items)
    assert chunk([], 2, 1) == ()


def _plan(*weeks):
    from datetime import date

    return TermPlan(
        term_id="t",
        sessions_per_week=5,
        class_during_exams=None,
        lost_days=(),
        enrichment_lessons=frozenset(),
        enrichment_examples={},
        weeks=tuple(
            PlanWeek(i + 1, date(2026, 9, 1), date(2026, 9, 5), tuple(w)) for i, w in enumerate(weeks)
        ),
    )


def test_scope_is_lessons_since_last_exam_or_that_exams_scope():
    plan = _plan(
        [PlanEntry("lesson", 2, "1.1"), PlanEntry("exam", 1, scope="midterm")],
        [PlanEntry("support", 1), PlanEntry("lesson", 1, "1.2"), PlanEntry("review", 1, scope="final")],
    )
    periods = plan_periods("c", plan)
    by_kind = {p.kind: p for p in periods}
    assert scope_lessons(periods, by_kind["exam"]) == ("1.1",)
    assert scope_lessons(periods, by_kind["support"]) == ("1.1",)  # لا درس بعد الاختبار: نطاقه
    assert scope_lessons(periods, by_kind["review"]) == ("1.2",)


def _prep(**changes) -> NonLessonPrep:
    base = {
        "course": "c",
        "slug": "quiz-u1",
        "kind": "quiz",
        "title": "",
        "unit": 1,
        "k": 1,
        "n": 1,
        "scope": ("1.1",),
        "warmup": "",
        "warmup_minutes": 5,
        "rows": (Row("", "", "", 5, "", "", 25),),
        "closing": "",
        "closing_minutes": 10,
        "homework": "",
        "papers": (),
        "missing_paper": "",
    }
    return NonLessonPrep(**{**base, **changes})


def test_checks_fail_on_minutes_scope_and_missing_paper():
    results = {c.code: c.status for c in check_non_lesson(_prep(closing_minutes=11, scope=()))}
    assert results == {"N1": "fail", "N2": "fail", "N3": "fail"}
    assert {c.code: c.status for c in check_non_lesson(_prep(kind="exam"))}["N3"] == "pending"
    assert {c.code: c.status for c in check_non_lesson(_prep(kind="project"))}["N3"] == "pass"
    assert {c.code: c.status for c in check_non_lesson(_prep(kind="orientation", scope=()))}["N2"] == "pass"


@pytest.mark.django_db
@pytest.mark.usefixtures("loaded_courses")
def test_grade10_has_fifteen_non_lesson_periods_of_45_minutes():
    items = selectors.non_lesson_preps(GRADE10_SLUG)
    assert len(items) == 15
    assert {i.prep.kind for i in items} == set(KINDS)
    for item in items:
        assert item.prep.minutes == 45
        statuses = {c.code: c.status for c in item.checks}
        assert statuses["N1"] == statuses["N2"] == "pass"


@pytest.mark.django_db
@pytest.mark.usefixtures("loaded_courses")
def test_grade10_paper_links_follow_the_owner_decision():
    items = {(i.prep.slug, i.prep.k): i for i in selectors.non_lesson_preps(GRADE10_SLUG)}
    quiz = items[("quiz-u1", 1)].prep
    assert quiz.scope == ("1.1", "1.2", "1.3")
    assert [(p.kind, p.lessons) for p in quiz.papers] == [("quiz", ("1.2", "1.3"))]
    review = [items[("review-midterm", k)].prep for k in (1, 2)]
    assert review[0].scope + review[1].scope == ("1.1", "1.2", "1.3", "2.1", "2.2", "2.3", "2.5", "2.6")
    assert all(p.kind == "worksheet" and p.level == "" for r in review for p in r.papers)
    support = items[("support", 1)].prep
    assert support.scope == review[0].scope  # الدعم بعد الاختبار: دروس نطاقه
    assert {p.level for p in support.papers} == {"K"}
    exam = items[("exam-midterm", 1)]
    assert exam.prep.papers == ()  # لا جدول مواصفات لمنتصف فصل العاشر
    assert {c.code: c.status for c in exam.checks}["N3"] == "pending"
    final = items[("review-final", 1)].prep
    assert any(p.kind == "bundle" and p.blueprint for p in final.papers)


@pytest.mark.django_db
@pytest.mark.usefixtures("loaded_courses")
def test_period_list_has_all_63_periods_in_plan_order(teacher_client):
    rows = teacher_client.get(f"{API}/{GRADE10_SLUG}").json()
    assert len(rows) == 63
    assert sum(r["kind"] == "lesson" for r in rows) == 48
    assert rows[0]["kind"] == "orientation" and rows[0]["lesson"] == "orientation"
    assert rows[2]["lesson"] == "1.1"


@pytest.mark.django_db
@pytest.mark.usefixtures("loaded_courses")
def test_every_non_lesson_prep_opens_and_downloads_word(teacher_client):
    for item in selectors.non_lesson_preps(GRADE10_SLUG):
        path = f"{API}/{GRADE10_SLUG}/{item.prep.slug}/{item.prep.k}"
        data = teacher_client.get(path).json()
        assert data["kind"] == item.prep.kind and data["edit"] is None
        assert len(data["papers"]) == len(item.prep.papers)
        response = teacher_client.get(f"{path}/word")
        assert response.status_code == 200
        text = document_text(response.content)
        assert not TOKEN.search(text), path
        assert item.prep.title in text


@pytest.mark.django_db
@pytest.mark.usefixtures("loaded_courses")
def test_unknown_non_lesson_period_is_404_and_cannot_be_edited(teacher_client):
    assert teacher_client.get(f"{API}/{GRADE10_SLUG}/quiz-u9/1").status_code == 404
    assert teacher_client.get(f"{API}/{GRADE10_SLUG}/review-midterm/3").status_code == 404
    response = teacher_client.put(
        f"{API}/{GRADE10_SLUG}/quiz-u1/1/override",
        {"strategies": {}, "removed": []},
        content_type="application/json",
    )
    assert response.status_code == 404
    assert re.search("quiz-u1", response.json()["detail"])
