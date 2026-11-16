"""عرض الدرس: ترتيب الشرائح من الفهرس وسير الحصة، وسلامة حزمة PPTX (RTL، علاقات، نسب الصور، حتمية)."""

import json
import re
import struct
import zipfile
import zlib
from io import BytesIO
from posixpath import dirname, join, normpath

import pytest
from lxml import etree

from apps.planning.domain.deck import (
    BulletsSlide,
    DeckError,
    ExampleClip,
    ExampleSlide,
    LessonContent,
    TableSlide,
    TitleSlide,
)
from apps.planning.example_clips import load_example_clips
from apps.planning.pptx_export import HEIGHT, WIDTH, build_pptx, fit
from apps.planning.selectors import lesson_codes, lesson_deck

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
RAW_BOOK_REFS = re.compile(r"For Qatar|Savvas|ISBN", re.IGNORECASE)


def _png(w: int, h: int) -> bytes:
    """PNG أبيض صالح بلا مكتبة صور (Pillow ليست من تبعيات المشروع)."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(b"\x00" + b"\xff\xff\xff" * w for _ in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    signature = b"\x89PNG\r\n\x1a\n"
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def _clip(n: int, w: int = 968, h: int = 795) -> ExampleClip:
    return ExampleClip(n=n, png=_png(w, h), width_px=w, height_px=h)


def _content(**kw) -> LessonContent:
    base = {
        "title": "عنوان تجريبي",
        "objectives": ("هدف أول", "هدف ثانٍ"),
        "vocabulary": (("مميّز", "discriminant"),),
        "examples": (_clip(2), _clip(1, 1003, 938)),
    }
    return LessonContent(**{**base, **kw})


def test_slide_order_follows_the_lesson_not_the_input_order():
    deck = lesson_deck("2.6", _content(), 45)
    kinds = [type(s).__name__ for s in deck.slides]
    assert kinds == [
        "TitleSlide",
        "BulletsSlide",
        "TableSlide",
        "ExampleSlide",
        "ExampleSlide",
        "TableSlide",
        "TableSlide",
    ]
    assert [s.title for s in deck.slides if isinstance(s, ExampleSlide)] == ["مثال 1", "مثال 2"]
    assert isinstance(deck.slides[0], TitleSlide) and "2.6" in deck.slides[0].subtitle


def test_missing_inputs_are_omitted_not_invented():
    deck = lesson_deck("2.6", _content(objectives=(), vocabulary=(), examples=()), 45)
    assert [type(s) for s in deck.slides] == [TitleSlide, TableSlide, TableSlide]
    assert not any(isinstance(s, BulletsSlide) for s in deck.slides)


def test_example_notes_come_from_the_index():
    deck = lesson_deck("2.6", _content(examples=(_clip(2),)), 45)
    notes = next(s for s in deck.slides if isinstance(s, ExampleSlide)).notes
    assert any(n.startswith("التمثيلات: ") for n in notes)


def test_example_outside_the_index_is_an_error():
    with pytest.raises(DeckError):
        lesson_deck("2.6", _content(examples=(_clip(19),)), 45)


def test_duplicate_example_and_empty_title_are_errors():
    with pytest.raises(DeckError):
        lesson_deck("2.6", _content(examples=(_clip(1), _clip(1))), 45)
    with pytest.raises(DeckError):
        lesson_deck("2.6", _content(title="  "), 45)


def test_unknown_lesson_raises():
    with pytest.raises(KeyError):
        lesson_deck("9.9", _content(), 45)


def test_clip_must_be_a_real_png_with_dimensions():
    with pytest.raises(DeckError):
        ExampleClip(n=1, png=b"JPEG", width_px=10, height_px=10)
    with pytest.raises(DeckError):
        ExampleClip(n=1, png=_png(2, 2), width_px=0, height_px=10)


@pytest.mark.parametrize("period", [40, 45, 60])
def test_flow_slide_minutes_sum_to_the_period(period):
    deck = lesson_deck("3.1", _content(examples=()), period)
    flow = next(s for s in deck.slides if isinstance(s, TableSlide) and s.title == "سير الحصة")
    assert sum(int(row[2]) for row in flow.rows) == period
    assert len(flow.rows) == 6


def test_fit_keeps_aspect_and_stays_inside_the_box():
    cx, cy = fit(968, 795, 6_000_000, 4_900_000)
    assert cx <= 6_000_000 and cy <= 4_900_000
    assert cx / cy == pytest.approx(968 / 795, rel=1e-3)
    assert cx == 6_000_000 or cy == 4_900_000  # يملأ البعد المقيِّد


def _parts(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(BytesIO(data)) as z:
        assert z.testzip() is None
        return {n: z.read(n) for n in z.namelist()}


def test_pptx_package_is_wellformed_and_self_consistent():
    deck = lesson_deck("2.6", _content(), 45)
    parts = _parts(build_pptx(deck))
    assert next(iter(parts)) == "[Content_Types].xml"
    for name, data in parts.items():
        if name.endswith((".xml", ".rels")):
            etree.fromstring(data)  # XML سليم

    types = etree.fromstring(parts["[Content_Types].xml"])
    overrides = {e.get("PartName") for e in types if e.tag.endswith("Override")}
    for name in parts:
        if name.startswith(
            ("ppt/slides/slide", "ppt/slideMasters/slideMaster", "ppt/slideLayouts/slideLayout", "ppt/theme/")
        ):
            if name.endswith(".xml"):
                assert "/" + name in overrides, name
    assert {f"/ppt/slides/slide{k}.xml" for k in range(1, len(deck.slides) + 1)} <= overrides

    # كل علاقة داخلية تشير إلى جزء موجود
    for name, data in parts.items():
        if not name.endswith(".rels"):
            continue
        base = dirname(dirname(name))
        for rel in etree.fromstring(data):
            assert normpath(join(base, rel.get("Target"))) in parts, (name, rel.get("Target"))


def test_pptx_is_rtl_16_9_with_one_slide_per_deck_slide():
    deck = lesson_deck("2.6", _content(), 45)
    parts = _parts(build_pptx(deck))
    pres = etree.fromstring(parts["ppt/presentation.xml"])
    assert pres.get("rtl") == "1"
    size = pres.find(f"{P}sldSz")
    assert (int(size.get("cx")), int(size.get("cy"))) == (WIDTH, HEIGHT) and WIDTH * 9 == HEIGHT * 16
    assert len(pres.find(f"{P}sldIdLst")) == len(deck.slides)
    for k in range(1, len(deck.slides) + 1):
        slide = etree.fromstring(parts[f"ppt/slides/slide{k}.xml"])
        paragraphs = slide.iter(f"{A}p")
        assert all(p.find(f"{A}pPr").get("rtl") == "1" for p in paragraphs if p.find(f"{A}pPr") is not None)
        for tbl in slide.iter(f"{A}tblPr"):
            assert tbl.get("rtl") == "1"


def test_example_image_keeps_its_aspect_and_lies_inside_the_slide():
    deck = lesson_deck("2.6", _content(examples=(_clip(1, 1003, 938),)), 45)
    parts = _parts(build_pptx(deck))
    k = next(i for i, s in enumerate(deck.slides, start=1) if isinstance(s, ExampleSlide))
    slide = etree.fromstring(parts[f"ppt/slides/slide{k}.xml"])
    sizes = []
    for pic in slide.iter(f"{P}pic"):
        off, ext = pic.find(f".//{A}off"), pic.find(f".//{A}ext")
        x, y, cx, cy = int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy"))
        assert 0 <= x and x + cx <= WIDTH and 0 <= y and y + cy <= HEIGHT
        sizes.append(cx / cy)
    assert any(r == pytest.approx(1003 / 938, rel=1e-3) for r in sizes)  # صورة المثال (الشعار بنسبته الأخرى)


def test_pptx_is_deterministic():
    deck = lesson_deck("2.6", _content(), 45)
    assert build_pptx(deck) == build_pptx(deck)


@pytest.mark.parametrize("code", lesson_codes())
def test_every_lesson_builds_a_deck_and_a_valid_package(code):
    deck = lesson_deck(code, _content(examples=()), 45)
    parts = _parts(build_pptx(deck))
    text = b" ".join(v for n, v in parts.items() if n.startswith("ppt/slides/slide")).decode("utf-8")
    assert not RAW_BOOK_REFS.search(text)
    assert code in text


def _write_clips(root, index: dict[str, list[dict]], sizes: dict[str, tuple[int, int]]):
    for name, (w, h) in sizes.items():
        (root / name).write_bytes(_png(w, h))
    (root / "index.json").write_text(json.dumps(index), encoding="utf-8")


def test_loader_reads_main_and_continuation_clips_in_order(tmp_path):
    _write_clips(
        tmp_path,
        {
            "2.6": [
                {"n": 2, "page": 7, "file": "a2.png", "cont": ["a2c.png"]},
                {"n": 1, "page": 6, "file": "a1.png", "cont": []},
                {"n": 3, "page": 8, "file": None, "cont": []},
            ]
        },
        {"a1.png": (40, 30), "a2.png": (50, 60), "a2c.png": (50, 20)},
    )
    clips = load_example_clips(tmp_path, "2.6")
    assert [(c.n, c.part, c.width_px, c.height_px) for c in clips] == [
        (1, 1, 40, 30),
        (2, 1, 50, 60),
        (2, 2, 50, 20),
    ]
    deck = lesson_deck("2.6", _content(examples=clips), 45)
    titles = [s.title for s in deck.slides if isinstance(s, ExampleSlide)]
    assert titles == ["مثال 1", "مثال 2", "تابع المثال 2"]
    cont = [s for s in deck.slides if isinstance(s, ExampleSlide)][2]
    assert cont.notes == ()
    assert build_pptx(deck)[:2] == b"PK"


def test_loader_errors_are_loud(tmp_path):
    with pytest.raises(DeckError):
        load_example_clips(tmp_path, "2.6")  # لا index.json
    _write_clips(tmp_path, {"2.6": [{"n": 1, "file": "missing.png", "cont": []}]}, {})
    with pytest.raises(DeckError):
        load_example_clips(tmp_path, "2.6")  # ملف مذكور غير موجود
    with pytest.raises(DeckError):
        load_example_clips(tmp_path, "9.9")  # درس غير مفهرس
    _write_clips(tmp_path, {"2.6": [{"n": 1, "file": "../x.png", "cont": []}]}, {})
    with pytest.raises(DeckError):
        load_example_clips(tmp_path, "2.6")  # خروج من المجلد
    (tmp_path / "bad.png").write_bytes(b"not a png at all, just text bytes")
    _write_clips(tmp_path, {"2.6": [{"n": 1, "file": "bad.png", "cont": []}]}, {})
    with pytest.raises(DeckError):
        load_example_clips(tmp_path, "2.6")


def test_continuation_of_unindexed_example_is_an_error():
    with pytest.raises(DeckError):
        lesson_deck(
            "2.6", _content(examples=(ExampleClip(n=9, png=_png(5, 5), width_px=5, height_px=5, part=2),)), 45
        )
