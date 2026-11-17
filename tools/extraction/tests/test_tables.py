"""جدول تحليل التمارين: هندسة صناديق مختلقة، لا نص دليل حقيقي ولا OCR."""

import json

import pytest

from tools.extraction import ocr, stamps, tables
from tools.extraction.__main__ import main

from .conftest import make_book

TITLE = ("تحليل التمارين", [400, 100, 700, 140])
HEADS = [
    ("المثال", [600, 150, 680, 180]),
    ("التمارين", [480, 150, 580, 180]),
    ("العمق المعرفي", [380, 150, 470, 180]),
]
CELLS = [
    ("1-2", [500, 200, 560, 230]),  # تمارين الصف الأول
    ("1", [410, 200, 430, 230]),  # عمقه
    ("1", [630, 225, 650, 255]),  # المثال المدموج على الصفين
    ("3", [500, 260, 520, 290]),
    ("2", [410, 260, 430, 290]),
]
BOXES = [TITLE, *HEADS, *CELLS]


def fake_lines(x0, x1, y0, y1):
    return [190, 245, 300] if x0 < 540 else [190, 300]  # عمود التمارين صفّان، عمود المثال خلية واحدة


def test_parse_numbers_ranges_and_lists():
    assert tables.parse_numbers("1-3، 5") == [1, 2, 3, 5]
    assert tables.parse_numbers("7") == [7]
    assert tables.parse_numbers("9-3") == []
    assert tables.parse_numbers("") == []


def test_parse_rows_merged_example_and_dok():
    rows = tables.parse(BOXES, "x.png", lines=fake_lines)
    assert [(r["example"], r["exercises"], r["dok"]) for r in rows] == [(1, [1, 2], 1), (1, [3], 2)]


def test_parse_none_without_title_or_headers_or_cells():
    assert tables.parse(HEADS + CELLS, "x.png", lines=fake_lines) is None
    assert tables.parse([TITLE, *CELLS], "x.png", lines=fake_lines) is None
    assert tables.parse([TITLE, *HEADS], "x.png", lines=fake_lines) is None


def test_parse_swapped_headers_resolved_by_cell_count():
    swapped = [("المثال", HEADS[2][1]), ("التمارين", HEADS[1][1]), ("العمق المعرفي", HEADS[0][1])]
    cells = [(t, b) for t, b in CELLS]
    rows = tables.parse([TITLE, *swapped, *cells], "x.png", lines=fake_lines)
    assert [(r["example"], r["dok"]) for r in rows] == [(1, 1), (1, 2)]


def test_parse_without_lines_groups_by_distance():
    rows = tables.parse(BOXES, "x.png", lines=lambda *a: [])
    # كالأصل: خلية المثال وحدها مجموعة بلا تمارين، ويُسقطها build لاحقًا
    assert [r["exercises"] for r in rows if r["exercises"]] == [[1, 2], [3]]


def test_task_guide_pairs_cells_with_headers_and_joins_wrapped_cell():
    boxes = [
        ("أساسي", [300, 100, 380, 130]),
        ("متقدم", [100, 100, 180, 130]),
        ("1-5", [310, 150, 360, 180]),
        ("6-9", [110, 150, 160, 180]),
        ("10", [315, 185, 350, 215]),  # التفاف خلية الأساسي على سطر ثانٍ
    ]
    assert tables.task_guide(boxes) == {"advanced": "6-9", "basic": "1-5 10"}
    assert tables.task_guide([("x", [0, 0, 1, 1])]) == {}


def test_custom_headers_and_title_from_config(tmp_path):
    book = make_book(
        tmp_path,
        {1: "Exercise Analysis"},
        dirs={"tables": "tables"},
        tables={
            "title": "Exercise Analysis",
            "headers": {"Example": "example", "Exercises": "exercises", "DOK": "dok"},
        },
    )
    assert tables.table_pages(book) == [1]
    boxes = [
        ("Exercise Analysis", TITLE[1]),
        ("Example", HEADS[0][1]),
        ("Exercises", HEADS[1][1]),
        ("DOK", HEADS[2][1]),
        *CELLS,
    ]
    rows = tables.parse(boxes, "x.png", tables.settings(book), fake_lines)
    assert [r["exercises"] for r in rows] == [[1, 2], [3]]


def test_hlines_finds_horizontal_rules(tmp_path):
    pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")
    img = Image.new("L", (800, 400), 255)
    draw = ImageDraw.Draw(img)
    for y in (100, 200):
        draw.rectangle([0, y - 1, 799, y + 1], fill=128)
    path = tmp_path / "p.png"
    img.save(path)
    assert tables.hlines(path, 50, 150, 0, 300) == [100, 200]


def _book(tmp_path):
    return make_book(tmp_path, {1: "غلاف", 2: "تحليل التمارين", 3: "نص آخر"}, dirs={"tables": "tables"})


def test_build_and_write_per_page_files_and_summary(tmp_path):
    book = _book(tmp_path)
    result = tables.build(book, lambda n: BOXES, fake_lines)
    assert list(result) == [2]
    assert "y" not in result[2]["rows"][0]
    tables.write(book, result)
    on_disk = json.loads((book.dir("tables") / "0002.json").read_text(encoding="utf-8"))
    assert on_disk["rows"][0]["exercises"] == [1, 2]
    assert json.loads(book.output("tables").read_text(encoding="utf-8"))["rows"] == 2


def test_write_never_deletes_existing_page_files(tmp_path):
    book = _book(tmp_path)
    book.dir("tables").mkdir()
    old = book.dir("tables") / "0099.json"
    old.write_text("{}", encoding="utf-8")
    tables.write(book, {})
    assert old.exists()


def test_page_without_example_label_is_dropped(tmp_path):
    book = _book(tmp_path)
    boxes = [b for b in BOXES if b[1] != [630, 225, 650, 255]]
    assert tables.build(book, lambda n: boxes, fake_lines) == {}


def test_stage_runs_and_is_skipped_when_inputs_unchanged(tmp_path, monkeypatch, capsys):
    book = _book(tmp_path)
    monkeypatch.setattr(ocr, "boxes", lambda b, n: BOXES)
    monkeypatch.setattr(tables, "hlines", lambda image, *a, cfg=None: fake_lines(*a))
    assert main([str(book.root), "tables"]) == 0
    assert (book.dir("tables") / "0002.json").exists()
    capsys.readouterr()
    assert main([str(book.root), "tables"]) == 0
    assert "تُخطيت" in capsys.readouterr().out
    (book.dir("render")).mkdir()
    (book.dir("render") / "0002.png").write_bytes(b"x")  # مدخل جديد يبطل الختم
    assert (
        stamps.digest(book, "tables")
        != json.loads((book.out / stamps.FILE).read_text(encoding="utf-8"))["tables"]
    )
