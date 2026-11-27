"""مرحلة exercise_pages بصناديق مصطنعة لا نص دليل."""

import json

from tools.extraction import exercise_pages
from tools.extraction.__main__ import main

from .conftest import TOY_PAGES, make_book


def _box(text, y):
    return [text, [100, y, 140, y + 20]]


def test_chain_skips_stray_numbers_and_keeps_page_order():
    got = exercise_pages.chain([(10, {1, 2, 3, 40}), (11, {2, 4, 6})], 5)
    assert got == {1: 10, 2: 10, 3: 10, 4: 11, 6: 11}


def test_status():
    assert exercise_pages.status({}, 3) == "missing"
    assert exercise_pages.status({1: 5, 2: 5}, 2) == "ok"
    assert exercise_pages.status({1: 5, 3: 5}, 3) == "review"
    assert exercise_pages.status({1: 5}, 0) == "review"


def test_stage_reads_only_after_marker_and_writes_ranges(tmp_path):
    book = make_book(
        tmp_path,
        TOY_PAGES,
        markers={"opener": "x", "exercises": "تمارين"},
        dirs={"ocr": "ocr", "student_ocr": "student_ocr"},
    )
    book.output("layout").write_text(
        json.dumps({"lessons": [{"id": "1.1", "pages_pdf": [2, 4]}]}), encoding="utf-8"
    )
    book.output("printed_pages").write_text(json.dumps({"2": 5, "3": 6, "4": 7}), encoding="utf-8")
    book.output("student_pages").write_text(json.dumps({"13": 5, "14": 6, "15": 7}), encoding="utf-8")
    (tmp_path / "student_ocr").mkdir()
    pages = {
        13: [_box("1", 50)],  # قبل قسم التمارين: رقم خطوة لا تمرين
        14: [_box("9", 30), _box("تمارين", 100), _box("1.", 200), _box("2.", 300)],
        15: [_box("3.", 50), _box("4.", 90)],
    }
    for n, boxes in pages.items():
        (tmp_path / "student_ocr" / f"{n:04d}.json").write_text(json.dumps(boxes), encoding="utf-8")

    assert main([str(tmp_path), "exercise_pages"]) == 0

    lesson = json.loads(book.output("exercise_pages").read_text(encoding="utf-8"))["lessons"]["1.1"]
    assert lesson["value"] == [{"first": 1, "last": 2, "page": 6}, {"first": 3, "last": 4, "page": 7}]
    assert lesson["status"] == "review"  # لا سجل درس يحدد العدد


def test_numbers_from_standalone_leading_and_arabic_trailing():
    boxes = [
        _box("1.", -5),
        _box("2. f(x)", 40),
        _box("0.8x", 70),
        _box("أوجد القيمة .3", 100),
        _box("9.", 0),
    ]
    assert exercise_pages.numbers(boxes, 60, top=20) == {2, 3}
    assert exercise_pages.numbers(boxes[:1], 60) == {1}


def test_spans_end_before_next_lesson():
    printed = list(range(1, 40))
    got = exercise_pages.spans([5, None, 9, 30], printed)
    assert got[0] == [5, 6, 7, 8] and got[1] == [] and got[2][-1] == 22 and got[3][0] == 30
