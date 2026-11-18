"""المصادر والخطة الفصلية والتقويم والاختبارات السابقة والتغطية: العقد يرفض المعيب، والمحمِّل يملأ الجداول idempotent،
والقراءة من الجداول تطابق الملف القانوني."""

import json

import pytest
from django.db import IntegrityError, transaction
from pydantic import ValidationError

from apps.curriculum.courses import GRADE10_SLUG, GRADE12_SLUG
from apps.curriculum.models import (
    AcademicCalendar,
    Blueprint,
    CalendarEvent,
    Course,
    Lesson,
    PastExam,
    PastExamItem,
    PlanEnrichment,
    PlanEntry,
    PlanWeek,
    ResourceCoverage,
    SourceDocument,
    TermPlan,
)
from apps.knowledge.domain.contract import CourseKnowledge, read_calendars, read_source, source_index
from apps.knowledge.selectors import course_index
from apps.knowledge.services import load_all, load_calendars, load_contract
from apps.planning.selectors import calendar_terms, term_plan

SHA = "ab" * 32
OTHER_SHA = "cd" * 32


def g10() -> dict:
    return json.loads(json.dumps(read_source(GRADE10_SLUG).model_dump(mode="json")))


def with_evidence(data: dict) -> dict:
    """العاشر ومعه اختبار سابق ومذكرة بمصدريهما: أعداد فقط."""
    data["sources"] += [
        {"slug": "g10-final-2025", "kind": "past_exam", "title": "نهائي ف1 2025-2026", "academic_year": "2025-2026", "digest": f"sha256:{SHA}"},
        {"slug": "g10-notes", "kind": "notes", "title": "مذكرة الوحدة 1", "academic_year": "2026-2027", "digest": f"sha256:{OTHER_SHA}"},
    ]  # fmt: skip
    data["past_exams"] = [
        {
            "slug": "g10-s1-2025-26-final",
            "source": "g10-final-2025",
            "academic_year": "2025-2026",
            "semester": 1,
            "assessment": "final",
            "total_marks": 10,
            "unmapped_marks": 2,
            "items": [
                {"question_number": 1, "lesson": "1.1", "kind": "mcq", "marks": 2, "level": "K", "dok": 1},
                {"question_number": 2, "lesson": "2.6", "kind": "essay", "marks": 6, "level": "A", "dok": 2},
            ],
        }
    ]
    data["coverage"] = [
        {
            "source": "g10-notes",
            "lessons": [{"lesson": "1.1", "items": 12, "solved": 12, "mcq": 4, "essay": 8}],
        }
    ]
    return data


# ───── العقد ─────


def test_both_courses_carry_their_academic_year_and_sources():
    for slug in (GRADE10_SLUG, GRADE12_SLUG):
        knowledge = read_source(slug)
        assert knowledge.course.academic_year == "2026-2027"
        assert {s.kind for s in knowledge.sources} == {"teacher_guide", "term_plan"}
    assert read_source(GRADE10_SLUG).term_plan.source == "g10-s1-term-plan"


def test_course_without_academic_year_is_rejected():
    data = g10()
    del data["course"]["academic_year"]
    with pytest.raises(ValidationError, match="academic_year"):
        CourseKnowledge(**data)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d["sources"].append({**d["sources"][0], "slug": "copy"}), "بتجزئة واحدة"),
        (lambda d: d["term_plan"].update(source="nowhere"), "غير مذكور"),
        (lambda d: d["term_plan"].update(source="g10-s1-teacher-guide"), "من نوع teacher_guide"),
        (lambda d: d["blueprints"][0].update(source="g10-s1-term-plan"), "من نوع term_plan"),
        (lambda d: d["past_exams"][0].update(total_marks=11), "مجموعها 10 والمعلن 11"),
        (lambda d: d["past_exams"][0]["items"][0].update(lesson="9.9"), "خارج المقرر"),
        (lambda d: d["coverage"][0]["lessons"][0].update(solved=13), "المحلول أو الأنواع"),
        (lambda d: d["coverage"][0].update(source="g10-final-2025"), "من نوع past_exam"),
    ],
)
def test_contract_rejects_broken_references_and_totals(change, message):
    data = with_evidence(g10())
    CourseKnowledge(**data)  # الأصل سليم
    change(data)
    with pytest.raises(ValueError, match=message):
        CourseKnowledge(**data)


def test_enrichment_lesson_must_not_be_examinable():
    data = g10()
    next(ref for ref in data["lessons"] if ref["code"] == "1.4")["examinable"] = True
    with pytest.raises(ValueError, match="مُعلَّم اختباريًا"):
        CourseKnowledge(**data)


def test_term_plan_is_checked_by_the_planning_engine():
    data = g10()
    data["term_plan"]["weeks"][0]["items"][1]["periods"] = 4  # أسبوع بست حصص
    with pytest.raises(ValidationError, match="حصص أسبوع 1: 6، والمتوقع 5"):  # PlanningError من المحرك نفسه
        CourseKnowledge(**data)


def test_empty_optional_sections_do_not_change_the_hash():
    data = g10()
    plain = CourseKnowledge(**data).content_hash()
    assert CourseKnowledge(**{**data, "past_exams": [], "coverage": []}).content_hash() == plain
    assert CourseKnowledge(**with_evidence(data)).content_hash() != plain


def test_calendar_file_is_named_after_its_year(tmp_path):
    (tmp_path / "2027-2028.json").write_text(
        json.dumps({**read_calendars()[0].model_dump(mode="json"), "year": "2026-2027"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="لا يطابق سنته"):
        read_calendars(tmp_path)


# ───── المحمِّل والجداول ─────


@pytest.mark.django_db
def test_load_all_fills_every_table_once():
    load_all()
    assert Course.objects.filter(academic_year="2026-2027").count() == 2
    assert SourceDocument.objects.count() == 4
    plan = TermPlan.objects.get(course__slug=GRADE10_SLUG)
    assert plan.source.slug == "g10-s1-term-plan"
    assert PlanWeek.objects.filter(plan=plan).count() == 13
    assert sum(PlanEntry.objects.filter(week__plan=plan).values_list("periods", flat=True)) == 63
    whole = PlanEnrichment.objects.filter(plan=plan, example__isnull=True)
    assert sorted(whole.values_list("lesson__code", flat=True)) == ["1.4", "2.4", "3.1", "3.2"]
    assert PlanEnrichment.objects.filter(plan=plan, example__isnull=False).count() == 10
    calendar = AcademicCalendar.objects.get(year="2026-2027")
    assert calendar.terms.count() == 2 and CalendarEvent.objects.filter(term__calendar=calendar).count() == 4

    assert all(report.total == 0 for report in load_all().values())
    assert sum(load_calendars().values()) == 0


@pytest.mark.django_db
def test_tables_are_the_reading_source_and_match_the_canonical_files():
    load_all()
    assert course_index(GRADE10_SLUG) == source_index(GRADE10_SLUG)
    assert term_plan(GRADE10_SLUG) == read_source(GRADE10_SLUG).term_plan.to_domain(1)
    terms = calendar_terms("2026-2027")
    assert (terms["t1"].start.isoformat(), terms["t2"].end.isoformat()) == ("2026-08-30", "2027-06-02")
    with pytest.raises(KeyError, match="لا خطة فصلية"):
        term_plan(GRADE12_SLUG)


@pytest.mark.django_db
def test_editing_the_plan_replaces_only_what_changed():
    load_all()
    data = g10()
    data["term_plan"]["notes"].append("ملاحظة جديدة")
    report = load_contract(CourseKnowledge(**data))
    assert report.changed["term_plan"] == 1 and report.changed["plan_weeks"] == 0  # الأسابيع لم تتغير

    week = data["term_plan"]["weeks"][1]["items"]
    week[0]["periods"], week[1]["periods"] = 2, 3  # 1.2 حصتان و1.3 ثلاث
    report = load_contract(CourseKnowledge(**data))
    assert report.changed["plan_weeks"] == 13
    assert PlanEntry.objects.get(week__plan__course__slug=GRADE10_SLUG, week__number=2, order=1).periods == 2


@pytest.mark.django_db
def test_past_exams_and_coverage_load_as_numbers_and_stay_idempotent():
    load_all()
    data = with_evidence(g10())
    report = load_contract(CourseKnowledge(**data))
    assert (report.changed["past_exams"], report.changed["past_exam_items"], report.changed["coverage"]) == (
        1,
        2,
        1,
    )
    exam = PastExam.objects.get(slug="g10-s1-2025-26-final")
    assert (exam.source.kind, exam.academic_year, exam.unmapped_marks) == ("past_exam", "2025-2026", 2)
    assert list(exam.items.values_list("lesson__code", "dok")) == [("1.1", 1), ("2.6", 2)]
    assert ResourceCoverage.objects.get(source__slug="g10-notes").solved == 12
    assert load_contract(CourseKnowledge(**data)).total == 0

    data["past_exams"][0]["items"].pop()
    data["past_exams"][0]["total_marks"] = 4
    report = load_contract(CourseKnowledge(**data))
    assert report.changed["past_exam_items"] == 1 and PastExamItem.objects.filter(exam=exam).count() == 1


@pytest.mark.django_db
def test_blueprint_records_its_assessment_scope_and_one_official_per_exam():
    load_all()
    final = Blueprint.objects.get(course__slug=GRADE10_SLUG, is_forecast=False, assessment="final")
    assert (final.assessment, final.scope) == ("final", "full")
    with pytest.raises(IntegrityError), transaction.atomic():
        Blueprint.objects.create(
            slug="g10-duplicate",
            course=final.course,
            title="نسخة",
            academic_year=final.academic_year,
            semester=final.semester,
            total_marks=50,
            is_forecast=False,
        )
    makeup = Blueprint.objects.get(course=final.course, is_forecast=False, assessment="makeup")
    assert (makeup.academic_year, makeup.semester, makeup.scope) == (
        final.academic_year,
        final.semester,
        "full",
    )
    Blueprint.objects.create(  # المتوقَّع قد يتعدد للاختبار نفسه
        slug="g10-forecast",
        course=final.course,
        title="توقع",
        academic_year=final.academic_year,
        semester=final.semester,
        total_marks=50,
    )


@pytest.mark.django_db
def test_database_constraints_guard_plan_rows():
    load_all()
    week = PlanWeek.objects.filter(plan__course__slug=GRADE10_SLUG).first()
    with pytest.raises(IntegrityError), transaction.atomic():
        PlanEntry.objects.create(week=week, order=99, kind="lesson", periods=1)  # درس بلا درس
    with pytest.raises(IntegrityError), transaction.atomic():
        PlanEntry.objects.create(week=week, order=98, kind="quiz", periods=1)  # اختبار وحدة بلا وحدة
    plan = week.plan
    lesson = Lesson.objects.get(course__slug=GRADE10_SLUG, code="1.4")
    with pytest.raises(IntegrityError), transaction.atomic():
        PlanEnrichment.objects.create(plan=plan, lesson=lesson)  # الدرس الإثرائي كله مسجَّل مرة
