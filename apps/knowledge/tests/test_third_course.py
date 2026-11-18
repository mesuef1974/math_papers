"""جاهزية الكتب الـ24: كتاب ثالث يدخل بمجلد بيانات وحده، بلا تعديل شيفرة، ولا يختلط بغيره في أي طبقة."""

import json
import shutil

import pytest
from django.db import IntegrityError, transaction

from apps.assets.models import Asset
from apps.assets.tests.conftest import teacher_client  # noqa: F401
from apps.curriculum.courses import GRADE10_SLUG, GRADE12_SLUG
from apps.curriculum.models import Course, Lesson
from apps.knowledge import models as km
from apps.knowledge.domain import contract
from apps.knowledge.domain.contract import CourseKnowledge, read_source, source_slugs
from apps.knowledge.selectors import course_index, course_index_from_tables, knowledge_state, lesson_index
from apps.knowledge.services import load_all, load_course
from apps.knowledge.tests.test_course_index import field, lesson_output
from apps.planning import selectors as planning
from apps.planning import services as planning_services
from apps.planning.domain.calendar_engine import PlanningError
from apps.planning.domain.deck import DeckError
from apps.planning.domain.feedback import ClassOutcome
from apps.planning.models import ClassOutcomeRecord

pytestmark = pytest.mark.django_db

THIRD = "g11-sci-s1"
# رموز تتقاطع عمدًا مع العاشر (1.1 و2.1) وتزيد عليه (2.10 و11.2: وحدة بخانتين)
THIRD_LESSONS = ("1.1", "2.1", "2.2", "2.10", "11.2")


@pytest.fixture
def third_course(tmp_path, monkeypatch):
    """مقرر ثالث يُبنى بأمر الاستخراج العام في نسخة من مجلدات المقررات: لا سطر شيفرة يعرفه."""
    from django.core.management import call_command

    root = tmp_path / "courses"
    shutil.copytree(contract.COURSES_DIR, root)
    monkeypatch.setattr(contract, "COURSES_DIR", root)
    records = tmp_path / "book" / "lessons"
    records.mkdir(parents=True)
    for code in THIRD_LESSONS:
        unit = code.split(".")[0]
        record = lesson_output(id=code, unit=unit, standards=field(["11.4.1", "10.2.2"]))
        (records / f"lesson_{code.replace('.', '_')}.json").write_text(json.dumps(record), encoding="utf-8")
    call_command(
        "build_course_index",
        THIRD,
        source=str(tmp_path / "book"),
        courses_dir=str(root),
        title="الرياضيات: الحادي عشر العلمي، الفصل الأول",
        grade=11,
        semester=1,
        academic_year="2026-2027",
        track="العلمي",
        language="en",
    )
    return root / THIRD


def test_a_new_folder_registers_the_course_everywhere(third_course):
    assert source_slugs() == [GRADE10_SLUG, THIRD, GRADE12_SLUG]
    knowledge = read_source(THIRD)
    assert isinstance(knowledge, CourseKnowledge)
    assert [ref.code for ref in knowledge.lessons] == list(THIRD_LESSONS)  # ترتيب عددي: 2.10 بعد 2.2
    assert {tuple(p.standards) for p in knowledge.profiles} == {("11.4.1",)}  # معايير صفه وحده

    reports = load_all()
    assert set(reports) == {GRADE10_SLUG, THIRD, GRADE12_SLUG}
    assert all(report.total == 0 for report in load_all().values())  # idempotent للثلاثة
    assert knowledge_state() == {GRADE10_SLUG: "ok", THIRD: "ok", GRADE12_SLUG: "ok"}

    course = Course.objects.get(slug=THIRD)
    assert (course.grade, course.track, course.semester, course.language) == (11, "العلمي", 1, "en")
    assert not course.is_current
    assert km.KnowledgeRelease.objects.filter(course=course).count() == 1
    assert course_index_from_tables(THIRD).model_dump() == course_index(THIRD).model_dump()


def test_lessons_are_ordered_numerically_in_the_tables(third_course):
    load_course(THIRD)
    rows = Lesson.objects.filter(course__slug=THIRD)
    assert [row.code for row in rows] == list(THIRD_LESSONS)
    assert [(row.unit, row.number) for row in rows] == [(1, 1), (2, 1), (2, 2), (2, 10), (11, 2)]
    profiles = km.LessonProfile.objects.filter(lesson__course__slug=THIRD)
    assert [p.lesson.code for p in profiles] == list(THIRD_LESSONS)


def test_planning_reads_each_course_from_its_own_index(third_course):
    load_all()  # الجداول مصدر القراءة الوحيد: المجلد وحده لا يكفي
    assert planning.lesson_codes(THIRD) == list(THIRD_LESSONS)
    assert len(planning.lesson_codes()) == 19  # الافتراضي مقرر الخطة الفصلية (العاشر)
    assert planning.lesson_profile("11.2", course=THIRD).dok == {1, 2}
    with pytest.raises(KeyError, match=THIRD):
        planning.lesson_profile("3.5", course=THIRD)  # درس في العاشر لا في هذا المقرر
    with pytest.raises(KeyError, match=GRADE10_SLUG):
        planning.lesson_profile("11.2")
    assert lesson_index(THIRD, "2.1").standards == ["11.4.1"]
    assert lesson_index(GRADE10_SLUG, "2.1").standards != ["11.4.1"]


def test_deck_never_borrows_another_course_lesson(third_course):
    """قبل الإصلاح كان العرض يقرأ فهرس العاشر أيًّا كان المقرر، فيبني درس الثاني عشر 2.6 بملف درس العاشر 2.6."""
    load_all()
    lesson = Lesson.objects.get(course__slug=GRADE12_SLUG, code="2.6")
    Asset.objects.create(
        course=lesson.course,
        lesson=lesson,
        kind=Asset.Kind.EXAMPLE,
        number=1,
        key="assets/test/g12-2.6-1.png",
        sha256="0" * 64,
        size=10,
        width=4,
        height=3,
    )
    with pytest.raises(DeckError, match="فهرس المقرر"):
        planning_services.prepare_deck(GRADE12_SLUG, "2.6", 45)


def test_class_records_of_two_courses_never_collide(third_course, django_user_model):
    load_all()
    teacher = django_user_model.objects.create_user("t-two-grades", password="x")  # noqa: S106
    first, _ = planning_services.record_outcome(teacher, "10/3", ClassOutcome("2.1", 30, 12))
    second, created = planning_services.record_outcome(
        teacher, "10/3", ClassOutcome("2.1", 28, 25), course=THIRD
    )
    assert created and ClassOutcomeRecord.objects.count() == 2
    assert first.lesson.course.slug == GRADE10_SLUG and second.lesson.course.slug == THIRD
    again, created_again = planning_services.record_outcome(
        teacher, "10/3", ClassOutcome("2.1", 28, 20), course=THIRD
    )
    assert not created_again and again.pk == second.pk and again.correct == 20
    with pytest.raises(PlanningError, match="غير موجود في المقرر"):
        planning_services.record_outcome(teacher, "10/3", ClassOutcome("3.5", 30, 12), course=THIRD)
    with pytest.raises(PlanningError, match="المقرر غير موجود"):
        planning_services.record_outcome(teacher, "10/3", ClassOutcome("2.1", 30, 12), course="nope")


def test_courses_endpoint_lists_every_loaded_course(third_course, teacher_client, client):  # noqa: F811
    load_all()
    rows = teacher_client.get("/api/v1/courses").json()
    assert [row["slug"] for row in rows] == [GRADE10_SLUG, THIRD, GRADE12_SLUG]  # بالصف فالمسار فالفصل
    third = rows[1]
    assert third == {
        "slug": THIRD,
        "title": "الرياضيات: الحادي عشر العلمي، الفصل الأول",
        "grade": 11,
        "track": "العلمي",
        "semester": 1,
        "edition": "",
        "language": "en",
        "is_current": False,
        "lesson_count": len(THIRD_LESSONS),
        "has_generators": False,
    }
    assert [row["has_generators"] for row in rows] == [True, False, True]  # للعاشر مولّدات الوحدة 1
    assert teacher_client.get(f"/api/v1/lessons?course={THIRD}").json()[3]["code"] == "2.10"
    client.logout()
    assert client.get("/api/v1/courses").status_code == 401


def test_contract_rejects_inconsistent_courses(third_course):
    base = read_source(THIRD).model_dump()
    wrong_unit = json.loads(json.dumps(base))
    wrong_unit["lessons"][0]["unit"] = 2
    with pytest.raises(ValueError, match="لا تطابق رمزه"):
        CourseKnowledge(**wrong_unit)
    with pytest.raises(ValueError, match="أكثر من ملف"):
        CourseKnowledge(**{**base, "profiles": base["profiles"] + base["profiles"][:1]})
    with pytest.raises(ValueError):
        CourseKnowledge(**{**base, "course": {**base["course"], "language": "fr"}})
    with pytest.raises(ValueError):
        CourseKnowledge(**{**base, "course": {**base["course"], "grade": 13}})
    # مجلد لا يطابق معرّف مقرره يُرفض عند القراءة
    stray = third_course.parent / "g9-s1"
    shutil.copytree(third_course, stray)
    with pytest.raises(ValueError, match="لا يطابق معرّف المقرر"):
        read_source("g9-s1")


def test_database_enforces_course_integrity():
    course = Course.objects.get(slug=GRADE12_SLUG)
    with pytest.raises(IntegrityError), transaction.atomic():  # الكتاب نفسه مرتين بمعرّفين
        Course.objects.create(
            slug="g12-copy",
            title="نسخة",
            grade=course.grade,
            track=course.track,
            semester=course.semester,
            edition=course.edition,
            academic_year=course.academic_year,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Course.objects.create(slug="g13", title="صف غير موجود", grade=13, semester=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        Course.objects.create(slug="g5-s4", title="فصل رابع", grade=5, semester=4)
    with pytest.raises(IntegrityError), transaction.atomic():
        Lesson.objects.create(course=course, code="0.1", title="وحدة صفر", unit=0)
