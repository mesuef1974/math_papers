"""مصدر فكرة السؤال في كتاب الطالب: رقم الصفحة المطبوعة ورقم المثال، مشتقًّا من مثال الصيغة وفهرس المقرر، أرقامًا فقط."""

import re

import pytest

from apps.curriculum.courses import GRADE10_SLUG
from apps.knowledge.selectors import course_index
from apps.papers import services
from apps.papers.api import PartOut
from apps.papers.domain.book_source import book_source, source_label
from apps.papers.domain.generators import SKILL_EXAMPLES, skill_example

FINAL = "g10-s1-2026-27-final"
LABEL = re.compile(r"^ص \d{1,3}، مثال \d{1,2}$")


def test_label_is_page_then_item_and_numbers_only():
    assert source_label(book_source(1, 28)) == "ص 28، مثال 1"
    assert source_label(book_source(4, 35, "practice")) == "ص 35، تدريب 4"
    assert source_label(book_source(2, None)) == "مثال 2"  # الصفحة غير معروفة: لا تُخترع
    assert book_source(None, 28) is None and source_label(None) == ""


@pytest.mark.usefixtures("loaded_courses")
def test_every_declared_grade10_example_has_a_printed_page():
    pages = {(row.lesson, e.n): e.page for row in course_index(GRADE10_SLUG).lessons for e in row.examples}
    for (course, lesson, _), number in SKILL_EXAMPLES.items():
        if course == GRADE10_SLUG:
            assert pages[(lesson, number)], (lesson, number)


@pytest.mark.usefixtures("loaded_courses")
@pytest.mark.parametrize("form", ["A", "B"])
def test_every_part_of_the_grade10_exam_carries_its_book_source(form):
    pages = {(row.lesson, e.n): e.page for row in course_index(GRADE10_SLUG).lessons for e in row.examples}
    paper = services.build_exam(FINAL, 7, form)
    parts = [part for question in paper["questions"] for part in question["parts"]]
    assert parts
    for part in parts:
        number = skill_example(GRADE10_SLUG, part["lesson"], part["variant"])
        assert part["source"] == {
            "kind": "example",
            "number": number,
            "page": pages[(part["lesson"], number)],
        }
        label = PartOut.model_validate(part).source_label
        assert LABEL.match(label) and label.endswith(f"مثال {number}"), label


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
