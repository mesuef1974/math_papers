"""مصدر فكرة السؤال في كتاب الطالب: رقم الصفحة المطبوعة ورقم المثال، مشتقًّا من مثال الصيغة وفهرس المقرر، أرقامًا فقط."""

import re

import pytest

from apps.curriculum.courses import GRADE10_SLUG
from apps.knowledge.selectors import course_index
from apps.papers import services
from apps.papers.api import PartOut
from apps.papers.domain.book_source import book_source, source_cells, source_label
from apps.papers.domain.generators import SKILL_EXAMPLES, skill_example

FINAL = "g10-s1-2026-27-final"
LABEL = re.compile(r"^ص \d{1,3}، مثال \d{1,2}(، تدريب \d+(?:–\d+)?(?:، \d+(?:–\d+)?)*)?$")


def test_label_is_page_then_item_and_numbers_only():
    assert source_label(book_source(1, 28)) == "ص 28، مثال 1"
    assert source_label(book_source(4, 35, "practice")) == "ص 35، تدريب 4"
    assert source_label(book_source(2, None)) == "مثال 2"  # الصفحة غير معروفة: لا تُخترع
    assert book_source(None, 28) is None and source_label(None) == ""


def test_label_lists_the_book_exercises_of_the_example_with_runs_as_ranges():
    assert source_label(book_source(2, 27, exercises=[28, 9, 11, 16, 17, 18, 19, 27])) == (
        "ص 27، مثال 2، تدريب 9، 11، 16–19، 27، 28"
    )
    assert source_label(book_source(1, 26, exercises=[20, 21])) == "ص 26، مثال 1، تدريب 20، 21"
    assert "exercises" not in book_source(1, 26, exercises=[])  # بلا تدريبات: المصدر كما كان


@pytest.mark.usefixtures("loaded_courses")
def test_every_declared_grade10_example_has_a_printed_page():
    pages = {(row.lesson, e.n): e.page for row in course_index(GRADE10_SLUG).lessons for e in row.examples}
    for (course, lesson, _), number in SKILL_EXAMPLES.items():
        if course == GRADE10_SLUG:
            assert pages[(lesson, number)], (lesson, number)


@pytest.mark.usefixtures("loaded_courses")
@pytest.mark.parametrize("form", ["A", "B"])
def test_every_part_of_the_grade10_exam_carries_its_book_source(form):
    lessons = course_index(GRADE10_SLUG).lessons
    pages = {(row.lesson, e.n): e.page for row in lessons for e in row.examples}
    exercises: dict = {}
    for row in lessons:
        for group in row.analysis:
            exercises.setdefault((row.lesson, group.example), set()).update(group.exercises)
    paper = services.build_exam(FINAL, 7, form)
    parts = [part for question in paper["questions"] for part in question["parts"]]
    assert parts
    for part in parts:
        number = skill_example(GRADE10_SLUG, part["lesson"], part["variant"])
        expected = {"kind": "example", "number": number, "page": pages[(part["lesson"], number)]}
        if exercises.get((part["lesson"], number)):
            expected["exercises"] = sorted(exercises[(part["lesson"], number)])
        assert part["source"] == expected
        label = PartOut.model_validate(part).source_label
        assert LABEL.match(label) and re.search(f"مثال {number}(،|$)", label), label


@pytest.mark.usefixtures("loaded_courses")
def test_grade12_parts_have_no_book_source():
    paper = services.build_worksheet("3.1", 4, 5)
    for part in (p for q in paper["questions"] for p in q["parts"]):
        assert "source" not in part  # لا مفتاح: الورقة كما كانت قبل المصدر
        assert PartOut.model_validate(part).source_label == ""


@pytest.mark.usefixtures("loaded_courses")
def test_label_is_derived_and_not_taken_from_the_client():
    part = services.build_worksheet("1.1", 1, 3, course=GRADE10_SLUG)["questions"][0]["parts"][0]
    derived = PartOut.model_validate(part).source_label
    assert derived.startswith("ص ")
    assert PartOut.model_validate({**part, "source_label": "ص 999، مثال 9"}).source_label == derived
    old = {key: value for key, value in part.items() if key != "source"}  # ورقة محفوظة قبل المصدر
    assert PartOut.model_validate(old).source_label == ""


def test_source_cells_split_the_source_into_the_three_key_columns():
    """«الصفحة» و«المثال» و«التدريب» (قرار المالك 2026-11-19): أرقام فقط، والمجهول فارغ لا مخترع."""
    assert source_cells(book_source(2, 27, exercises=[28, 9, 11, 16, 17, 18, 19])) == {
        "page": "27",
        "example": "2",
        "exercises": "9، 11، 16–19، 28",
    }
    assert source_cells(book_source(2, None)) == {"page": "", "example": "2", "exercises": ""}
    assert source_cells(book_source(4, 35, "practice")) == {"page": "35", "example": "", "exercises": "4"}
    assert source_cells(None) == {"page": "", "example": "", "exercises": ""}


@pytest.mark.usefixtures("loaded_courses")
def test_source_cells_are_derived_and_not_taken_from_the_client():
    part = services.build_worksheet("1.1", 1, 3, course=GRADE10_SLUG)["questions"][0]["parts"][0]
    out = PartOut.model_validate({**part, "source_page": "999", "source_example": "9"})
    assert (out.source_page, out.source_example, out.source_exercises) == tuple(
        source_cells(part["source"]).values()
    )
    old = PartOut.model_validate({key: value for key, value in part.items() if key != "source"})
    assert (old.source_page, old.source_example, old.source_exercises) == ("", "", "")
