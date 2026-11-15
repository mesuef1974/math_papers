import json

import pytest

from tools.extraction import images

from .conftest import make_book


def test_keep_filters_icons_and_missing_xref():
    assert images.keep({"xref": 5, "width": 800, "height": 140}, (800, 140))
    assert not images.keep({"xref": 5, "width": 799, "height": 140}, (800, 140))
    assert not images.keep({"xref": 5, "width": 800, "height": 139}, (800, 140))
    assert not images.keep({"xref": 0, "width": 900, "height": 900}, (800, 140))


def test_entry_fields():
    e = images.entry(
        3,
        9,
        {"width": 10, "height": 20, "ext": "png", "image": b"abc", "smask": 0},
        {"bbox": (1.04, 2, 3, 4)},
        (595.27, 841.9),
        "x.png",
    )
    assert (e["page"], e["xref"], e["bytes"], e["has_smask"], e["page_size"], e["bbox"][0]) == (
        3,
        9,
        3,
        False,
        [595.3, 841.9],
        1.0,
    )
    assert len(e["sha256_12"]) == 12


def test_by_lesson_spans():
    layout = {"lessons": [{"id": "1.1", "pages_pdf": [2, 4]}, {"id": "1.2", "pages_pdf": None}]}
    index = [
        {"page": 1, "file": "a"},
        {"page": 3, "file": "b"},
        {"page": 4, "file": "c"},
        {"page": 9, "file": "d"},
    ]
    assert images.by_lesson(index, layout) == {"1.1": ["b", "c"]}


def test_extract_from_real_pdf(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    pytest.importorskip("PIL")
    from PIL import Image

    big, small = tmp_path / "big.png", tmp_path / "small.png"
    Image.new("RGB", (300, 120), "red").save(big)
    Image.new("RGB", (20, 20), "blue").save(small)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(10, 10, 310, 130), filename=str(big))
    page.insert_image(pymupdf.Rect(10, 200, 30, 220), filename=str(small))
    doc.save(tmp_path / "book.pdf")
    book = make_book(
        tmp_path, {1: "x"}, layout={"image_min": [100, 50]}, pdf={"dir": ".", "pattern": "book.pdf"}
    )
    index = images.extract(book)
    assert [(e["page"], e["width"], e["height"]) for e in index] == [(1, 300, 120)]
    assert (book.dir("student_pages") / index[0]["file"]).exists()
    assert json.loads((book.dir("student_pages") / "index.json").read_text(encoding="utf-8")) == index
    assert images.extract(book) == index  # idempotent
