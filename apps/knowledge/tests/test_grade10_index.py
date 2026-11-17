"""فهرس العاشر المشتق: المخطط صارم، والباني يُبقي الأرقام والفئات المغلقة فقط، والملف المودَع سليم ولا نص دليل فيه."""

import json
import re

import pytest
from pydantic import ValidationError

from apps.knowledge.domain.grade10_index import (
    BLOOM_VALUES,
    Grade10Index,
    Grade10Lesson,
    build_index,
    build_lesson_index,
)
from apps.knowledge.selectors import GRADE10_INDEX, grade10_index, grade10_lesson


def field(value):
    return {"value": value, "source": "guide", "status": "ok"}


def lesson_output(**over):
    base = {
        "id": "2.1",
        "unit": "2",
        "standards": field(["10.2.2", "غير معيار"]),
        "practices": field([]),
        "objectives": field(
            [
                {"text": "نص هدف طويل من الدليل", "verb": "استعمال", "bloom": "تطبيق"},
                {"text": "نص آخر", "verb": "x", "bloom": None},
            ]
        ),
        "examples": [
            {
                "n": 2,
                "representation": field(["جدول", "جبري"]),
                "skill": field({"title": "عنوان", "focus": "س"}),
            },
            {"n": 1, "representation": field(["سياق حياتي", "بياني"])},
        ],
        "exercise_analysis": field(
            [
                {"example": 1, "dok": 1, "exercises": [3, 1, 2, 2]},
                {"example": 1, "dok": None, "exercises": [9]},
                {"example": 2, "dok": 2, "exercises": [4]},
            ]
        ),
        "exercises": field([1, 2, 3, 4, 9]),
        "task_guide": field({"basic": "1-4, 9", "advanced": "2-9"}),
        "lesson_quiz": field({"questions": 3, "depth": [1, 2, 2]}),
        "vocabulary": field(
            [
                {"ar": "حل", "en": "solution", "kind": "review"},
                {"ar": "معادلة", "en": "equation", "kind": "new"},
                {"ar": "صفر", "en": "zero", "kind": "new"},
            ]
        ),
    }
    return base | over


def test_builder_keeps_only_numbers_and_closed_categories():
    rec = build_lesson_index(lesson_output())
    assert rec["standards"] == ["10.2.2"]
    assert rec["objectives_bloom"] == ["تطبيق", "unclassified"]
    assert [e["n"] for e in rec["examples"]] == [1, 2]
    assert rec["examples"][0]["representations"] == ["بياني", "سياق"]  # «سياق حياتي» يُوحَّد
    assert rec["examples"][1]["representations"] == ["جدول", "جبري"]
    assert rec["analysis"] == [
        {"example": 1, "dok": 1, "exercises": [1, 2, 3]},
        {"example": 2, "dok": 2, "exercises": [4]},
    ]  # الصف بلا عمق لا يدخل
    assert rec["exercises_total"] == 9
    assert rec["task_guide"] == {"basic": "1-4, 9", "advanced": "2-9"}
    assert rec["quiz_depths"] == [1, 2, 2]
    assert rec["vocabulary"] == {"new": 2, "review": 1}
    assert Grade10Lesson(**rec)


def test_no_source_text_survives_the_builder():
    dumped = json.dumps(build_lesson_index(lesson_output()), ensure_ascii=False)
    for leaked in ("نص هدف", "عنوان", "معادلة", "solution", "استعمال"):
        assert leaked not in dumped


def test_task_guide_that_is_not_a_numeric_range_is_dropped():
    bad = lesson_output(task_guide=field({"basic": "انظر الدليل", "advanced": "2-9"}))
    assert build_lesson_index(bad)["task_guide"] is None


def test_schema_rejects_free_text_and_unknown_fields():
    rec = build_lesson_index(lesson_output())
    with pytest.raises(ValidationError):
        Grade10Lesson(**rec | {"title": "عنوان الدرس"})
    with pytest.raises(ValidationError):
        Grade10Lesson(**rec | {"objectives_bloom": ["نص حر"]})
    with pytest.raises(ValidationError):
        Grade10Lesson(**rec | {"task_guide": {"basic": "نص", "advanced": "1-2"}})
    with pytest.raises(ValidationError):
        Grade10Lesson(**rec | {"examples": [{"n": 1, "representations": ["غير معروف"]}]})


def test_index_orders_lessons_numerically():
    lessons = [lesson_output(id="2.10"), lesson_output(id="2.2"), lesson_output(id="1.4")]
    assert [x.lesson for x in build_index(lessons).lessons] == ["1.4", "2.2", "2.10"]


# --- الملف المودَع ---

EXPECTED = ["1.1", "1.2", "1.3", "1.4"] + [f"2.{n}" for n in range(1, 11)] + [f"3.{n}" for n in range(1, 6)]


def test_committed_index_is_valid_and_complete():
    index = grade10_index()
    assert [x.lesson for x in index.lessons] == EXPECTED
    for lesson in index.lessons:
        assert lesson.unit == int(lesson.lesson[0])
        assert lesson.examples, lesson.lesson
        assert lesson.practices, lesson.lesson
        assert lesson.analysis, lesson.lesson
        assert set(lesson.objectives_bloom) <= set(BLOOM_VALUES)
        example_numbers = {e.n for e in lesson.examples}
        assert {row.example for row in lesson.analysis} <= example_numbers, lesson.lesson
        flat = [n for row in lesson.analysis for n in row.exercises]
        assert max(flat) <= lesson.exercises_total, lesson.lesson


def test_committed_index_roundtrips_byte_for_byte():
    raw = GRADE10_INDEX.read_text(encoding="utf-8")
    again = json.dumps(Grade10Index(**json.loads(raw)).model_dump(), ensure_ascii=False, indent=1) + "\n"
    assert raw == again


def test_committed_index_holds_no_arabic_prose():
    """الحروف العربية الوحيدة المسموحة قيم القوائم المغلقة (بلوم وتمثيلات)؛ أي جملة تعني تسرّب نص."""
    allowed = {*BLOOM_VALUES, "جدول", "بياني", "جبري", "سياق"}
    strings = re.findall(r'"([^"]*[؀-ۿ][^"]*)"', GRADE10_INDEX.read_text(encoding="utf-8"))
    assert set(strings) <= allowed


def test_selector_finds_a_lesson():
    assert grade10_lesson("3.5").unit == 3
    assert grade10_lesson("9.9") is None
