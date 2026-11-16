import json

import pytest

from apps.curriculum.models import Lesson
from apps.knowledge import models as km
from apps.knowledge.domain import curation, schemas
from apps.knowledge.domain.contract import COURSES_DIR
from apps.knowledge.domain.schemas import LessonData, PedagogyData, UnitData
from apps.knowledge.selectors import coverage, template_counts
from apps.knowledge.services import load_knowledge

DATA_DIR = COURSES_DIR / "g12-sci-s1"
LESSON_FILES = sorted((DATA_DIR / "lessons").glob("lesson_*.json"))


def test_domain_vocabulary_matches_model_choices():
    assert set(schemas.KINDS) == {c.value for c in km.LessonItem.Kind}
    assert set(schemas.LEVELS) == {c.value for c in km.Level}
    assert set(schemas.BLOOMS) == {c.value for c in km.Bloom}
    assert set(schemas.CATEGORIES) == {c.value for c in km.ExerciseTemplate.Category}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("K", ("K", "")),
        ("A", ("A", "")),
        ("", ("", "")),
        ("K للتمارين 9-16، A للباقي", ("K", "K للتمارين 9-16، A للباقي")),
        ("x", ("", "x")),
    ],
)
def test_normalize_level(raw, expected):
    assert curation.normalize_level(raw) == expected


def test_normalize_bloom_takes_first_and_keeps_note():
    assert curation.normalize_bloom("تطبيق") == ("تطبيق", "")
    assert curation.normalize_bloom("تطبيق/تحليل") == ("تطبيق", "بلوم: تطبيق/تحليل")
    assert curation.normalize_bloom("غير معروف")[0] == ""


def test_numbers_and_counts():
    assert curation.numbers_in("36-40") == {36, 37, 38, 39, 40}
    assert curation.numbers_in("39, 40") == {39, 40}
    assert curation.exercise_count("1-6", None) == 6
    assert curation.exercise_count("x", 4) == 4


def test_category_map_skips_none_and_maps_ranges():
    mapping = curation.category_map({"استكشاف": "41-42", "توسيع الأفكار": "لا يوجد", "نشاط جماعي": "50"})
    assert mapping == {41: "exploration", 42: "exploration", 50: "group"}


def test_clean_drops_guarded_text_and_reports():
    report = curation.Report()
    assert curation.clean("جدول (ص43)", report, "t") == ""
    assert curation.clean("  نص   سليم ", report, "t") == "نص سليم"
    assert len(report.dropped) == 1


def test_guard_rejects_long_and_page_references():
    for bad in ("x" * 901, "من Savvas", "انظر الصفحة 12", "For Qatar MoE"):
        with pytest.raises(ValueError):
            schemas.safe_text(bad)


def test_committed_lessons_are_valid_and_clean():
    assert len(LESSON_FILES) == 19
    for path in LESSON_FILES:
        data = LessonData(**json.loads(path.read_text(encoding="utf-8")))
        assert path.stem == f"lesson_{data.lesson.replace('.', '_')}"
        assert data.objective and data.templates and data.items
        assert all(schemas.STANDARD_CODE.match(code) for code in data.standards) and data.standards
        assert all(len(t.skill) <= schemas.MAX_TEXT for t in data.templates)


def test_committed_units_and_pedagogy_are_valid():
    units = [UnitData(**u) for u in json.loads((DATA_DIR / "units.json").read_text(encoding="utf-8"))]
    notes = [PedagogyData(**n) for n in json.loads((DATA_DIR / "pedagogy.json").read_text(encoding="utf-8"))]
    assert [u.unit for u in units] == [1, 2, 3]
    assert len({n.slug for n in notes}) == len(notes) >= 10


@pytest.mark.django_db
def test_load_is_idempotent_and_creates_missing_lessons_from_source():
    Lesson.objects.filter(code="3.6").delete()  # المحمِّل ينشئ الدرس من المصدر نفسه لا يتخطاه
    first = load_knowledge()
    assert first.total > 0
    assert first.changed["lessons"] == 1
    counts = (
        km.LessonProfile.objects.count(),
        km.LessonItem.objects.count(),
        km.ExerciseTemplate.objects.count(),
    )
    assert counts[0] == Lesson.objects.count() == 19
    second = load_knowledge()
    assert second.total == 0
    assert (
        km.LessonProfile.objects.count(),
        km.LessonItem.objects.count(),
        km.ExerciseTemplate.objects.count(),
    ) == counts


@pytest.mark.django_db
def test_load_repairs_drifted_rows():
    load_knowledge()
    profile = km.LessonProfile.objects.get(lesson__code="1.1")
    profile.items.all().delete()
    profile.objective = "x"
    profile.save()
    report = load_knowledge()
    assert report.changed["items"] == 1 and report.changed["profiles"] == 1
    assert profile.items.exists()


@pytest.mark.django_db
def test_coverage_reports_gap_when_no_generator():
    load_knowledge()
    rows = coverage()
    assert rows and sum(r.templates for r in rows) == sum(template_counts().values())
    assert any(not r.generators for r in rows)  # فجوات حقيقية معروفة
    assert any(r.generators for r in rows)
