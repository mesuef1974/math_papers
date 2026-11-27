"""الربط اليدوي: ملف اختيار المالك يصير غلاف practice معتمدًا، والصفحة تحمل صفًّا لكل مثال (كتاب مختلق، لا نص دليل)."""

import json

import pytest

from tools.extraction import exercise_manual, stamps
from tools.extraction.__main__ import main
from tools.extraction.corrections import CorrectionError

from .conftest import TOY_PAGES, make_book

ID_PATTERN = r"(?<![\d.a-z])(\d{1,2})\.(\d{1,2})(?![\d.])"
LAYOUT = {"lessons": [{"id": "1.1", "pages_pdf": [2, 5]}]}
EXAMPLES = {"lessons": {"1.1": {"value": [{"n": 1, "start": 3}, {"n": 2, "start": 4}]}}}


@pytest.fixture
def book(tmp_path):
    got = make_book(tmp_path, TOY_PAGES, layout={"id_pattern": ID_PATTERN})
    (tmp_path / "render").mkdir()
    (tmp_path / "render" / "0005.png").write_bytes(b"png")
    return got


def _picks(book, lessons, name="toy"):
    exercise_manual.picks_path(book).write_text(
        json.dumps({"book": name, "lessons": lessons}), encoding="utf-8"
    )


def _row(example, *numbers):
    return {"example": example, "exercises": list(numbers)}


def _links(*examples):
    rows = [_row(e) for e in examples]
    return {"lessons": {"1.1": {"value": rows, "source": "derived", "status": "review"}}}


def test_picks_become_accepted_practice_and_are_idempotent(book):
    _picks(book, {"1.1": [_row(2, 5, 4, 4), _row(1, 2)]})
    result = _links(1, 2)
    exercise_manual.apply(book, result)
    practice = result["lessons"]["1.1"]["practice"]
    assert practice["value"] == [_row(1, 2), _row(2, 4, 5)]
    assert (practice["status"], practice["source"], practice["method"]) == ("ok", "teacher", "manual")
    again = json.loads(json.dumps(result))
    exercise_manual.apply(book, again)
    assert again == result


def test_without_picks_nothing_changes(book):
    result = _links(1)
    exercise_manual.apply(book, result)
    assert result == _links(1)


@pytest.mark.parametrize(
    "lessons,name",
    [
        ({"9.9": [_row(1, 2)]}, "toy"),
        ({"1.1": [_row(7, 2)]}, "toy"),
        ({"1.1": [_row(1, 0)]}, "toy"),
        ({"1.1": [{"example": 1}]}, "toy"),
        ({"1.1": [_row(1, 2)]}, "other"),
    ],
)
def test_bad_picks_are_rejected(book, lessons, name):
    _picks(book, lessons, name)
    with pytest.raises(CorrectionError):
        exercise_manual.apply(book, _links(1, 2))


def test_ranges_text():
    assert exercise_manual.ranges_text([3, 1, 2, 5, 7, 8]) == "1-3، 5، 7-8"
    assert exercise_manual.ranges_text([]) == ""


def test_page_has_a_row_per_example_with_saved_picks(book):
    _picks(book, {"1.1": [_row(2, 4, 5, 6)]})
    text, counts = exercise_manual.page_html(book, LAYOUT, EXAMPLES, _links(1, 2))
    assert counts == {"lessons": 1, "examples": 2, "pages": 1, "picked_lessons": 1}
    assert text.count("<input data-example=") == 2
    assert 'value="4-6"' in text and 'src="render/0005.png"' in text
    assert "$title" not in text and "$sections" not in text


def test_stage_writes_page_and_new_picks_rerun_links(book):
    root = str(book.out)
    assert main([root, "exercise_manual"]) == 0
    assert stamps.output_path(book, "exercise_manual").is_file()
    assert not exercise_manual.picks_path(book).exists()  # الملف للمالك لا للمرحلة
    before = stamps.digest(book, "exercise_links")
    _picks(book, {})
    assert stamps.digest(book, "exercise_links") != before
