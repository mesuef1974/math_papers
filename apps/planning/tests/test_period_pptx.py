"""ملف عرض الحصة (المرحلة 4، الجزء ب، من docs/lesson_prep_plan.md): التصدير ومعايير الملف S7 وS8 وS12.

حصص العاشر الـ48 تُصدَّر بمقاطع PNG حقيقية وتجتاز معايير الملف، ولكل معيار حالة فاشلة على ملف معدَّل أو مقطع رديء.
"""

import json
import zipfile
from io import BytesIO

import pytest
from lxml import etree

from apps.assets.tests.conftest import make_png
from apps.curriculum.courses import GRADE10_SLUG
from apps.planning.domain.deck import DeckError, ExampleClip, build_period_deck
from apps.planning.domain.prep_checks import FAIL, PASS
from apps.planning.example_clips import load_example_clips
from apps.planning.pptx_checks import (
    check_pptx,
    contrast,
    s7_clip_clarity,
    s8_identity,
    s12_package,
)
from apps.planning.pptx_export import BRAND, CONTENT_BOX, INK, WHITE, build_period_pptx, fit
from apps.planning.selectors import lesson_preps

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
CLEAR = make_png(1600, 900)


def clips_for(prep, png: bytes = CLEAR, width: int = 1600, height: int = 900) -> tuple[ExampleClip, ...]:
    return tuple(
        ExampleClip(n=e.n, png=png, width_px=width, height_px=height, part=part)
        for e in prep.examples
        for part in range(1, (e.continuations or 1) + 1)
    )


@pytest.fixture
def decks(loaded_courses):
    return [build_period_deck(row.prep, clips_for(row.prep)) for row in lesson_preps(GRADE10_SLUG)]


@pytest.fixture
def sample(decks):
    """عرض حصة فيها أمثلة وتتمة مثال إن وُجدت."""
    return next(d for d in decks if any(s.clip is not None for s in d.slides))


def _parts(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(BytesIO(data)) as z:
        assert z.testzip() is None
        return {n: z.read(n) for n in z.namelist()}


def _zip(parts: dict[str, bytes]) -> bytes:
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data in parts.items():
            z.writestr(name, data)
    return out.getvalue()


def _slides(parts: dict[str, bytes]) -> list[etree._Element]:
    names = sorted(
        (n for n in parts if n.startswith("ppt/slides/slide") and n.endswith(".xml")),
        key=lambda n: int(n[16:-4]),
    )
    return [etree.fromstring(parts[n]) for n in names]


# ---- الحصص الـ48 ----


@pytest.mark.django_db
def test_forty_eight_files_pass_file_checks_and_mirror_the_model(decks):
    assert len(decks) == 48
    for deck in decks:
        data = build_period_pptx(deck)
        assert [r.status for r in check_pptx(data, build_period_pptx(deck))] == [PASS, PASS, PASS], deck.key
        parts = _parts(data)
        slides = _slides(parts)
        assert len(slides) == len(deck.slides)
        assert sum(n.startswith("ppt/notesSlides/notesSlide") and n.endswith(".xml") for n in parts) == len(
            deck.slides
        )
        clip_pics = [
            pic
            for root in slides
            for pic in root.iter(f"{P}pic")
            if pic.find(f".//{P}cNvPr").get("name").startswith("مقطع")
        ]
        assert len(clip_pics) == sum(s.clip is not None for s in deck.slides)


@pytest.mark.django_db
def test_notes_alt_text_and_direction(sample):
    parts = _parts(build_period_pptx(sample))
    for k, slide in enumerate(sample.slides, 1):
        notes = etree.fromstring(parts[f"ppt/notesSlides/notesSlide{k}.xml"])
        assert "".join(notes.itertext()) == "".join(slide.notes)
        root = etree.fromstring(parts[f"ppt/slides/slide{k}.xml"])
        text = "".join(root.itertext())
        assert slide.title in text
        for note in slide.notes:  # جانب المعلم لا يظهر على الشريحة
            assert note not in text
        for p in root.iter(f"{A}p"):
            assert p.find(f"{A}pPr").get("rtl") == "1"
        if slide.clip is not None:
            pic = next(
                p for p in root.iter(f"{P}pic") if p.find(f".//{P}cNvPr").get("name").startswith("مقطع")
            )
            assert pic.find(f".//{P}cNvPr").get("descr") == slide.alt
    presentation = etree.fromstring(parts["ppt/presentation.xml"])
    assert presentation.get("rtl") == "1"


@pytest.mark.django_db
def test_files_open_in_python_pptx_with_notes_alt_text_and_no_empty_placeholder(decks):
    """شاهد مستقل عن قارئ pptx_checks: python-pptx يفتح الملفات الـ48 بشرائحها وملاحظاتها ونصوصها البديلة."""
    from pptx import Presentation

    for deck in decks:
        presentation = Presentation(BytesIO(build_period_pptx(deck)))
        assert len(presentation.slides) == len(deck.slides), deck.key
        for model, slide in zip(deck.slides, presentation.slides, strict=True):
            assert slide.has_notes_slide, deck.key
            assert slide.notes_slide.notes_text_frame.text.replace("\n", "") == "".join(model.notes)
            for placeholder in (*slide.placeholders, *slide.notes_slide.placeholders):
                assert placeholder.text_frame.text.strip(), (deck.key, model.title)
            texts = "".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)
            assert model.title in texts
            clips = [sh for sh in slide.shapes if sh.name.startswith("مقطع")]
            assert len(clips) == (model.clip is not None), (deck.key, model.title)
            for clip in clips:
                assert clip._element.nvPicPr.cNvPr.get("descr") == model.alt


@pytest.mark.django_db
def test_file_is_deterministic(sample):
    assert build_period_pptx(sample) == build_period_pptx(sample)


def test_fit_keeps_aspect_and_stays_inside_the_box():
    cx, cy = fit(968, 795, 6_000_000, 4_900_000)
    assert cx <= 6_000_000 and cy <= 4_900_000
    assert cx / cy == pytest.approx(968 / 795, rel=1e-3)
    assert cx == 6_000_000 or cy == 4_900_000  # يملأ البعد المقيِّد


def test_brand_pairs_meet_contrast():
    assert contrast(WHITE, BRAND) >= 4.5
    assert contrast(INK, WHITE) >= 4.5


# ---- حالة فاشلة لكل معيار ----


@pytest.mark.django_db
def test_s7_fails_for_low_resolution_and_for_short_clip(loaded_courses):
    prep = next(r.prep for r in lesson_preps(GRADE10_SLUG) if r.prep.examples)
    small = build_period_deck(prep, clips_for(prep, make_png(160, 90), 160, 90))
    result = s7_clip_clarity(build_period_pptx(small))
    assert result.status == FAIL and any("دقة" in d for d in result.details)
    wide = build_period_deck(prep, clips_for(prep, make_png(4000, 300), 4000, 300))
    result = s7_clip_clarity(build_period_pptx(wide))
    assert result.status == FAIL and any("ارتفاع منطقة المحتوى" in d for d in result.details)
    _, _, cx, cy = CONTENT_BOX
    assert fit(4000, 300, cx, cy)[1] < 0.6 * cy


def _tamper(data: bytes, part: str, old: bytes, new: bytes) -> bytes:
    parts = _parts(data)
    assert old in parts[part]
    parts[part] = parts[part].replace(old, new, 1)
    return _zip(parts)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (f'val="{INK}"'.encode(), b'val="00FF00"', "خارج الهوية"),
        (b'typeface="Cairo"', b'typeface="Arial"', "Cairo"),
        (
            f'sz="2800" b="0" dirty="0"><a:solidFill><a:srgbClr val="{INK}"'.encode(),
            b'sz="2800" b="0" dirty="0"><a:solidFill><a:srgbClr val="DB943C"',
            "الذهبي",
        ),
        (
            f'b="1" dirty="0"><a:solidFill><a:srgbClr val="{WHITE}"'.encode(),
            f'b="1" dirty="0"><a:solidFill><a:srgbClr val="{BRAND}"'.encode(),
            "تباين",
        ),
    ],
)
def test_s8_fails_on_foreign_color_font_gold_text_and_contrast(sample, old, new, message):
    data = build_period_pptx(sample)
    k = next(i for i, s in enumerate(sample.slides, 1) if s.bullets and s.kind != "title")
    result = s8_identity(_tamper(data, f"ppt/slides/slide{k}.xml", old, new))
    assert result.status == FAIL and any(message in d for d in result.details), result.details


@pytest.mark.django_db
def test_s12_fails_on_broken_package_empty_placeholder_and_nondeterminism(sample):
    data = build_period_pptx(sample)
    assert s12_package(data, data).status == PASS
    assert s12_package(data, data + b"x").status == FAIL  # غير حتمي
    assert s12_package(b"not a zip", b"not a zip").status == FAIL
    parts = _parts(data)
    media = next(n for n in parts if n.startswith("ppt/media/"))
    broken = _zip({n: v for n, v in parts.items() if n != media})
    assert any("غير موجود" in d for d in s12_package(broken, broken).details)
    bad_xml = _zip({**parts, "ppt/slides/slide1.xml": b"<p:sld"})
    assert any("لا يُقرأ" in d for d in s12_package(bad_xml, bad_xml).details)
    notes = parts["ppt/notesSlides/notesSlide1.xml"]
    emptied = etree.fromstring(notes)
    for t in emptied.iter(f"{A}t"):
        t.text = ""
    empty = _zip({**parts, "ppt/notesSlides/notesSlide1.xml": etree.tostring(emptied)})
    assert any("عنصر نائب فارغ" in d for d in s12_package(empty, empty).details)


# ---- محمِّل المقاطع المحلية ----


def _write_clips(root, index: dict[str, list[dict]], sizes: dict[str, tuple[int, int]]):
    for name, (w, h) in sizes.items():
        (root / name).write_bytes(make_png(w, h))
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


def test_clip_must_be_a_real_png_with_dimensions():
    with pytest.raises(DeckError):
        ExampleClip(n=1, png=b"JPEG", width_px=10, height_px=10)
    with pytest.raises(DeckError):
        ExampleClip(n=1, png=make_png(2, 2), width_px=0, height_px=10)
