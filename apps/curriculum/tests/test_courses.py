"""المقرر والمفاتيح المركبة: قاعدة تقبل كتابين برموز متطابقة، وبيانات الثاني عشر القائمة تنتقل إليه."""

import importlib

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.curriculum import selectors
from apps.curriculum.courses import GRADE12_SLUG
from apps.curriculum.models import Blueprint, Course, Lesson
from apps.knowledge.models import LessonProfile, PedagogyNote, UnitProfile
from apps.knowledge.services import load_knowledge
from apps.planning.models import ClassOutcomeRecord

pytestmark = pytest.mark.django_db

seed_migration = importlib.import_module("apps.curriculum.migrations.0008_seed_grade12_course")
assign_migration = importlib.import_module("apps.knowledge.migrations.0003_assign_grade12_course")


def second_course(slug: str = "g10-s1") -> Course:
    return Course.objects.create(slug=slug, title="العاشر", grade=10, semester=1)


def test_migration_seeds_grade12_as_the_current_course_with_all_rows_attached():
    course = Course.objects.get(slug=GRADE12_SLUG)
    assert course.is_current and (course.grade, course.semester) == (12, 1)
    assert selectors.current_course() == course
    assert Lesson.objects.count() > 0 and not Lesson.objects.filter(course__isnull=True).exists()
    assert Blueprint.objects.count() > 0 and not Blueprint.objects.filter(course__isnull=True).exists()


def test_seed_migrations_are_idempotent():
    from django.apps import apps

    seed_migration.forwards(apps, None)
    seed_migration.forwards(apps, None)
    assign_migration.forwards(apps, None)
    assert Course.objects.filter(slug=GRADE12_SLUG).count() == 1


def test_two_courses_hold_lessons_with_the_same_code():
    other = second_course()
    first = Lesson.objects.get(course__slug=GRADE12_SLUG, code="1.1")
    twin = Lesson.objects.create(course=other, code="1.1", title="درس آخر", unit=1)
    assert Lesson.objects.filter(code="1.1").count() == 2
    assert selectors.lessons(other).get(code="1.1") == twin
    assert selectors.lessons().get(code="1.1") == first  # بلا مقرر: الحالي


def test_duplicate_code_in_one_course_is_rejected_and_course_is_required():
    with pytest.raises(IntegrityError), transaction.atomic():
        Lesson.objects.create(course=Course.objects.get(slug=GRADE12_SLUG), code="1.1", title="مكرر", unit=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        Lesson.objects.create(course=None, code="9.1", title="بلا مقرر", unit=9)
    with pytest.raises(IntegrityError), transaction.atomic():
        Blueprint.objects.create(
            slug="no-course",
            course=None,
            title="بلا مقرر",
            academic_year="2026-2027",
            semester=1,
            total_marks=10,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        UnitProfile.objects.create(course=None, unit=9, title="بلا مقرر")
    with pytest.raises(IntegrityError), transaction.atomic():
        PedagogyNote.objects.create(course=None, slug="no-course", title="بلا مقرر", text="نص")
    user = get_user_model().objects.create(username="teacher")
    with pytest.raises(IntegrityError), transaction.atomic():
        ClassOutcomeRecord.objects.create(owner=user, section="10/1", lesson=None, attempted=1, correct=1)


def test_backfill_migrations_number_lessons_and_are_idempotent():
    """إعادة تعبئة التخطيط (planning 0003 و0005) تقرأ عمودًا حُذف في 0007، فلا تُشغَّل على النماذج الحالية."""
    from django.apps import apps

    number_migration = importlib.import_module(
        "apps.curriculum.migrations.0011_backfill_lesson_number_and_course"
    )
    knowledge_migration = importlib.import_module("apps.knowledge.migrations.0006_backfill_course")
    # دروس الثاني عشر زُرعت قبل عمود الرقم: الهجرة ملأته من الرمز
    seeded = {row.code: row.number for row in Lesson.objects.filter(course__slug=GRADE12_SLUG)}
    assert seeded["1.1"] == 1 and seeded["2.9"] == 9 and 0 not in seeded.values()
    Lesson.objects.filter(code="2.9").update(number=0)
    for _ in range(2):
        number_migration.forwards(apps, None)
        knowledge_migration.forwards(apps, None)
    assert Lesson.objects.get(course__slug=GRADE12_SLUG, code="2.9").number == 9


@pytest.mark.parametrize(
    ("module", "model"),
    [
        ("apps.papers.migrations.0006_saved_paper_course_guard", "SavedPaper"),
        ("apps.planning.migrations.0005_lesson_guard", "ClassOutcomeRecord"),
    ],
)
def test_contract_guard_stops_the_migration_when_a_row_is_still_unlinked(monkeypatch, module, model):
    """صف بقي بلا ربط بعد إعادة التعبئة يوقف الهجرة (فيفشل preDeploy) ولا يُحذف."""

    class Rows:
        def filter(self, **_):
            return self

        def count(self):
            return 1

    class Apps:
        def get_model(self, *_):
            return type(model, (), {"objects": Rows()})

    guard = importlib.import_module(module)
    monkeypatch.setattr(guard.BACKFILL, "forwards", lambda *_: None)
    with pytest.raises(RuntimeError, match="أعِد النشر"):
        guard.forwards(Apps(), None)


def test_only_one_course_is_current():
    with pytest.raises(IntegrityError), transaction.atomic():
        Course.objects.create(slug="x", title="x", grade=10, semester=1, is_current=True)


def test_unknown_course_is_reported():
    with pytest.raises(selectors.UnknownCourseError):
        selectors.course_by_slug("nope")


def test_loader_writes_only_to_its_own_course():
    other = second_course()
    twin = Lesson.objects.create(course=other, code="1.1", title="درس آخر", unit=1)
    load_knowledge()
    assert not LessonProfile.objects.filter(lesson=twin).exists()
    assert not UnitProfile.objects.exclude(course__slug=GRADE12_SLUG).exists()
    assert not PedagogyNote.objects.exclude(course__slug=GRADE12_SLUG).exists()
    assert load_knowledge().total == 0  # التحميل الثاني بلا تغيير


def test_units_and_notes_repeat_across_courses():
    other = second_course()
    load_knowledge()
    unit = UnitProfile.objects.filter(course__slug=GRADE12_SLUG).first()
    note = PedagogyNote.objects.filter(course__slug=GRADE12_SLUG).first()
    UnitProfile.objects.create(course=other, unit=unit.unit, title="وحدة أخرى")
    PedagogyNote.objects.create(course=other, slug=note.slug, title="مبدأ آخر", text="نص")
    with pytest.raises(IntegrityError), transaction.atomic():
        UnitProfile.objects.create(course=other, unit=unit.unit, title="مكرر")
