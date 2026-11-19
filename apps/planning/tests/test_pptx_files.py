"""ملف PPTX لعرض الحصة (المرحلة 4، الجزء ب، من docs/lesson_prep_plan.md): التصدير ومعاييره على الملف S7 وS8 وS12.

حصص العاشر الـ48 تُصدَّر ملفاتها وتجتاز المعايير، وتُفتح بـ python-pptx (تبعية تطوير) بشرائحها وملاحظاتها ونصوصها البديلة،
ولكل معيار حالة فاشلة على ملف معدَّل.
"""

import re
import zipfile
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest
from pptx import Presentation

from apps.assets.tests.conftest import make_png
from apps.planning import services
from apps.planning.domain.deck import CLIP_KINDS, DeckError, build_period_deck
from apps.planning.domain.prep_checks import FAIL, PASS
from apps.planning.pptx_checks import check_pptx, contrast, png_size, s7_clips, s8_identity, s12_package
from apps.planning.pptx_export import (
    BRAND,
    GOLD,
    INK,
    INK_SOFT,
    ROLE_CLIP,
    TOKENS,
    WHITE,
    build_period_pptx,
)

from .period_decks import CLIP_H, CLIP_PNG, CLIP_W, middle_of

TOKENS_CSS = Path(__file__).resolve().parents[3] / "frontend" / "src" / "styles" / "tokens.css"


@pytest.fixture
def files(built):
    """(التحضير، معاييره، المقاطع، العرض، الملف) لكل حصة."""
    return [(*b, build_period_pptx(b[3])) for b in built]


def _rezip(data: bytes, changes: dict[str, bytes | None]) -> bytes:
    """نسخة من الحزمة بجزء مستبدَل (بايتات) أو محذوف (None) أو مضاف."""
    edits = dict(changes)
    out = BytesIO()
    with zipfile.ZipFile(BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename in edits:
                if edits[info.filename] is not None:
                    dst.writestr(info, edits.pop(info.filename))
                continue
            dst.writestr(info, src.read(info.filename))
        for name, body in edits.items():
            if body is not None:
                dst.writestr(name, body)
    return out.getvalue()


def _part(data: bytes, name: str) -> str:
    with zipfile.ZipFile(BytesIO(data)) as z:
        return z.read(name).decode("utf-8")


def _clip_media(data: bytes) -> str:
    """مسار صورة أول مقطع في الحزمة، من علاقة الشكل نفسه."""
    for slide in Presentation(BytesIO(data)).slides:
        for shape in slide.shapes:
            if shape.name.startswith(ROLE_CLIP):
                return str(slide.part.related_part(shape._element.blip_rId).partname).lstrip("/")
    raise AssertionError("لا مقطع في العرض")


# ---- الحصص الـ48 ----


@pytest.mark.django_db
def test_forty_eight_files_pass_s7_s8_s12(files):
    assert len(files) == 48
    for prep, _, _, deck, data in files:
        failed = [(r.code, r.details) for r in check_pptx(data, deck) if r.status != PASS]
        assert not failed, (prep.lesson, prep.k, failed)


@pytest.mark.django_db
def test_files_open_in_python_pptx_with_notes_alt_text_and_no_empty_placeholder(files):
    for prep, _, _, deck, data in files:
        presentation = Presentation(BytesIO(data))
        assert len(presentation.slides) == len(deck.slides), (prep.lesson, prep.k)
        for model, slide in zip(deck.slides, presentation.slides, strict=True):
            assert slide.has_notes_slide
            assert slide.notes_slide.notes_text_frame.text == "\n".join(model.notes)
            for placeholder in (*slide.placeholders, *slide.notes_slide.placeholders):
                assert placeholder.text_frame.text.strip(), (prep.lesson, prep.k, model.kind)
            texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
            assert model.title in texts
            clips = [sh for sh in slide.shapes if sh.name.startswith(ROLE_CLIP)]
            assert len(clips) == (model.kind in CLIP_KINDS)
            for clip in clips:
                assert clip._element.nvPicPr.cNvPr.get("descr") == model.alt


@pytest.mark.django_db
def test_title_bar_uses_the_model_sizes_and_bullets_are_on_the_slide(files):
    _, _, _, deck, data = middle_of(files)
    presentation = Presentation(BytesIO(data))
    for model, slide in zip(deck.slides, presentation.slides, strict=True):
        runs = [
            r for sh in slide.shapes if sh.has_text_frame for p in sh.text_frame.paragraphs for r in p.runs
        ]
        title = next(r for r in runs if r.text == model.title)
        assert title.font.size.pt >= model.title_pt
        for bullet in model.bullets:
            run = next(r for r in runs if r.text == bullet)
            assert run.font.size.pt == model.body_pt


def test_palette_is_the_light_tokens():
    """كل لون في المصدِّر قيمة رمزه في كتلة :root النهارية من tokens.css."""
    root = TOKENS_CSS.read_text(encoding="utf-8").split(":root {", 1)[1].split("}", 1)[0]
    values = dict(re.findall(r"(--color-[\w-]+):\s*#([0-9a-fA-F]{6})", root))
    for color, token in TOKENS.items():
        assert values[token].upper() == color, token


def test_palette_contrast_of_the_pairs_in_use():
    assert contrast(WHITE, BRAND) >= 4.5 and contrast(INK, WHITE) >= 4.5
    assert contrast(GOLD, WHITE) < 4.5  # لذلك الذهبي زخرفة لا نص


# ---- خدمة التصدير ----


@pytest.mark.django_db
def test_export_returns_the_file_and_every_result(built):
    prep, prep_results, clips, deck = middle_of(built)
    data, results = services.export_period_deck(prep, clips, prep_results)
    assert data == build_period_pptx(deck)
    assert [r.code for r in results][-3:] == ["S7", "S8", "S12"]
    assert all(r.status != FAIL for r in results)


@pytest.mark.django_db
def test_export_refuses_a_blocking_failure_on_the_model_or_the_file(built):
    prep, prep_results, clips, _ = middle_of(built)
    unapproved = [replace(r, status=FAIL) if r.code == "T2c" else r for r in prep_results]
    with pytest.raises(DeckError, match="S1"):
        services.export_period_deck(prep, clips, unapproved)
    tiny = tuple(replace(c, png=make_png(160, 90), width_px=160, height_px=90) for c in clips)
    with pytest.raises(DeckError, match="S7"):
        services.export_period_deck(prep, tiny, prep_results)


# ---- حالة فاشلة لكل معيار ----


@pytest.mark.django_db
def test_s7_fails_on_a_low_resolution_or_short_clip(built):
    prep, _, clips, deck = middle_of(built)
    assert png_size(CLIP_PNG) == (CLIP_W, CLIP_H)
    assert s7_clips(build_period_pptx(deck)).status == PASS
    low = tuple(replace(c, png=make_png(320, 180), width_px=320, height_px=180) for c in clips)
    result = s7_clips(build_period_pptx(build_period_deck(prep, low)))
    assert result.status == FAIL and "بكسل لكل بوصة" in result.details[0]
    wide = tuple(replace(c, png=make_png(6000, 600), width_px=6000, height_px=600) for c in clips)
    result = s7_clips(build_period_pptx(build_period_deck(prep, wide)))
    assert result.status == FAIL and "من ارتفاع المحتوى" in result.details[0]


@pytest.mark.django_db
def test_s7_fails_when_the_clip_image_is_not_png(built):
    _, _, _, deck = middle_of(built)
    data = build_period_pptx(deck)
    broken = _rezip(data, {_clip_media(data): b"not a png"})
    assert s7_clips(broken).status == FAIL


@pytest.mark.django_db
def test_s8_fails_on_foreign_color_gold_text_low_contrast_and_title_font(built):
    _, _, _, deck = middle_of(built)
    data = build_period_pptx(deck)
    name = "ppt/slides/slide2.xml"
    xml = _part(data, name)
    assert s8_identity(data).status == PASS
    cases = {
        "ليس من رموز الهوية": xml.replace(f'val="{BRAND}"', 'val="123456"', 1),
        "بلون الزخرفة": xml.replace(
            f'<a:srgbClr val="{INK}"/></a:solidFill><a:latin',
            f'<a:srgbClr val="{GOLD}"/></a:solidFill><a:latin',
            1,
        ),
        "تباين": xml.replace(
            f'<a:srgbClr val="{WHITE}"/></a:solidFill><a:latin',
            f'<a:srgbClr val="{INK_SOFT}"/></a:solidFill><a:latin',
            1,
        ),
        "لا Cairo": xml.replace('typeface="Cairo"', 'typeface="Arial"'),
    }
    for message, changed in cases.items():
        assert changed != xml, message
        result = s8_identity(_rezip(data, {name: changed.encode()}))
        assert result.status == FAIL and any(message in d for d in result.details), (message, result)


@pytest.mark.django_db
def test_s12_fails_on_a_broken_package_an_empty_placeholder_or_another_deck(built):
    prep, _, clips, deck = middle_of(built)
    data = build_period_pptx(deck)
    assert s12_package(data, deck).status == PASS
    assert s12_package(b"PK not a zip", deck).status == FAIL
    assert s12_package(_rezip(data, {"ppt/slides/slide1.xml": None}), deck).status == FAIL
    assert s12_package(_rezip(data, {"ppt/extra.bin": b"x"}), deck).status == FAIL
    notes = "ppt/notesSlides/notesSlide1.xml"
    xml = _part(data, notes)
    emptied = re.sub(r"<a:p>.*</a:p>", "<a:p/>", xml, flags=re.S)
    result = s12_package(_rezip(data, {notes: emptied.encode()}), deck)
    assert result.status == FAIL and any("فارغ" in d for d in result.details)
    assert s12_package(data, replace(deck, slides=deck.slides[:-1])).status == FAIL  # عدد الشرائح
    retitled = replace(deck, slides=(replace(deck.slides[0], title="الدرس 9.9"), *deck.slides[1:]))
    result = s12_package(data, retitled)
    assert result.status == FAIL and any("بناءً جديدًا" in d for d in result.details)  # الحتمية


@pytest.mark.django_db
def test_file_is_deterministic_and_tracks_the_clip(built):
    prep, _, clips, deck = middle_of(built)
    assert build_period_pptx(deck) == build_period_pptx(build_period_deck(prep, clips))
    other = (replace(clips[0], png=make_png(CLIP_W, CLIP_H, shade=7)), *clips[1:])
    assert build_period_pptx(build_period_deck(prep, other)) != build_period_pptx(deck)
