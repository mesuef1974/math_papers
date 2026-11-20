"""صفحات تمارين الدرس في كتاب الطالب: المديات وتحققها، وكتابتها في ملف الدرس والفهرس، وتحميلها إلى الجداول وقراءتها منها."""

from __future__ import annotations

import json

import pytest
from django.core.management import call_command
from pydantic import ValidationError

from apps.knowledge.domain.book_numbers import with_exercise_pages
from apps.knowledge.domain.course_index import LessonIndex, build_index
from apps.knowledge.domain.exercise_pages import (
    ExercisePages,
    accepted_ranges,
    check_ranges,
    compress,
    page_map,
)
from apps.knowledge.domain.schemas import LessonData
from apps.papers.domain.book_source import numbers_with_pages

RANGES = [{"first": 1, "last": 9, "page": 11}, {"first": 10, "last": 17, "page": 12}]


def test_compress_and_page_map_round_trip():
    pages = dict.fromkeys(range(1, 10), 11) | dict.fromkeys(range(10, 18), 12) | {30: 14}
    assert compress(pages) == [*RANGES, {"first": 30, "last": 30, "page": 14}]
    assert page_map(compress(pages)) == pages


def test_ranges_must_be_ordered_disjoint_and_pages_non_decreasing():
    with pytest.raises(ValueError):
        ExercisePages(first=5, last=4, page=3)
    with pytest.raises(ValueError):
        check_ranges([ExercisePages(first=1, last=9, page=11), ExercisePages(first=9, last=12, page=12)])
    with pytest.raises(ValueError):
        check_ranges([ExercisePages(first=1, last=9, page=12), ExercisePages(first=10, last=12, page=11)])
    with pytest.raises(ValidationError):
        LessonData(lesson="1.1", exercise_pages=[RANGES[1], RANGES[0]])


def test_accepted_ranges_takes_ok_only_unless_review_is_asked():
    record = {"value": RANGES, "status": "review"}
    assert accepted_ranges(record) is None
    assert accepted_ranges(record, ("ok", "review")) == RANGES
    assert accepted_ranges({"value": RANGES, "status": "ok"}) == RANGES
    assert (
        accepted_ranges({"value": [{"first": 3, "last": 1, "page": 2}], "status": "ok"}) is None
    )  # شكل خاطئ
    assert accepted_ranges(None) is None


def test_numbers_with_pages_groups_by_page_and_keeps_unknown_bare():
    pages = page_map(RANGES)
    assert numbers_with_pages([14, 15], pages) == "14، 15 (ص 12)"
    assert numbers_with_pages([8, 10, 11, 12], pages) == "8 (ص 11)؛ 10–12 (ص 12)"
    assert numbers_with_pages([16, 40], pages) == "16 (ص 12)؛ 40"
    assert numbers_with_pages([3, 4], {}) == "3، 4"  # بلا صفحات: نص number_list نفسه


def test_with_exercise_pages_is_idempotent_and_keeps_key_position():
    lesson = {"lesson": "1.1", "standards": [], "examples": [{"number": 1}], "templates": []}
    once = with_exercise_pages(lesson, RANGES)
    assert list(once) == ["lesson", "standards", "exercise_pages", "examples", "templates"]
    assert with_exercise_pages(once, RANGES) == once
    assert with_exercise_pages(once, None) == once  # None يترك الملف كما كان
    moved = with_exercise_pages(once, RANGES[:1])
    assert list(moved) == list(once) and moved["exercise_pages"] == RANGES[:1]


def test_build_index_carries_accepted_ranges_only_for_its_lesson():
    lesson = {"id": "1.1", "unit": 1}
    index = build_index([lesson, {"id": "1.2", "unit": 1}], 10, exercise_pages={"1.1": RANGES})
    assert [r.model_dump() for r in index.lessons[0].exercise_pages] == RANGES
    assert index.lessons[1].exercise_pages == []
    assert "exercise_pages" in LessonIndex.model_fields


def _lesson_file(tmp_path, code="1.1"):
    courses = tmp_path / "courses"
    lessons = courses / "c1" / "lessons"
    lessons.mkdir(parents=True)
    path = lessons / f"lesson_{code.replace('.', '_')}.json"
    path.write_text(json.dumps({"lesson": code, "examples": [{"number": 1}]}), encoding="utf-8")
    return courses, path


def _source(tmp_path, status):
    source = tmp_path / "book"
    source.mkdir()
    (source / "examples.json").write_text(json.dumps({"lessons": {}}), encoding="utf-8")
    (source / "printed_pages.json").write_text("{}", encoding="utf-8")
    pages = {"lessons": {"1.1": {"value": RANGES, "status": status}}}
    (source / "exercise_pages.json").write_text(json.dumps(pages), encoding="utf-8")
    return source


@pytest.mark.parametrize(
    ("status", "review", "written"), [("ok", False, True), ("review", False, False), ("review", True, True)]
)
def test_write_book_numbers_writes_exercise_pages(tmp_path, status, review, written):
    courses, path = _lesson_file(tmp_path)
    source = _source(tmp_path, status)
    call_command(
        "write_book_numbers", "c1", source=str(source), courses_dir=str(courses), include_review=review
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert (data.get("exercise_pages") == RANGES) is written
    before = path.read_text(encoding="utf-8")
    call_command(
        "write_book_numbers", "c1", source=str(source), courses_dir=str(courses), include_review=review
    )
    assert path.read_text(encoding="utf-8") == before  # idempotent


@pytest.mark.django_db
def test_loader_writes_and_tables_read_exercise_pages(loaded_courses):
    from apps.knowledge.models import LessonProfile
    from apps.knowledge.selectors import course_index_from_tables

    profile = LessonProfile.objects.filter(lesson__course__slug="g10-s1").select_related("lesson").first()
    profile.exercise_pages = RANGES
    profile.save()
    index = course_index_from_tables("g10-s1")
    lesson = next(item for item in index.lessons if item.lesson == profile.lesson.code)
    assert [r.model_dump() for r in lesson.exercise_pages] == RANGES
