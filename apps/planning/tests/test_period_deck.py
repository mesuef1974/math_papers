"""عرض الحصة من تحضيرها (المرحلة 4، الجزء أ، من docs/lesson_prep_plan.md): النموذج ومعاييره S1 إلى S6 وS9 إلى S11 وS13.

حصص العاشر الـ48 تُبنى عروضها بمقاطع PNG وهمية وتجتاز المعايير كلها، وعدد شرائح الأمثلة يساوي أمثلة التحضير وتتماتها،
ولكل معيار حالة فاشلة.
"""

from dataclasses import replace

import pytest

from apps.papers.domain.bidi import LRM
from apps.planning.domain.deck import (
    DeckError,
    ExampleClip,
    PeriodSlide,
    build_period_deck,
    period_deck_key,
)
from apps.planning.domain.deck_checks import (
    check_deck,
    s1_input,
    s2_examples,
    s3_order,
    s3b_phases,
    s4_objectives,
    s5_pace,
    s6_density,
    s9_direction,
    s10_accessibility,
    s11_notes,
    s13_no_guide_text,
)
from apps.planning.domain.prep import prep_digest
from apps.planning.domain.prep_checks import FAIL, PASS, CheckResult

from .period_decks import CLIP_PNG as PNG
from .period_decks import fake_clips
from .period_decks import middle_of as _middle


def _fails(result: CheckResult) -> bool:
    return result.status == FAIL


# ---- الحصص الـ48 ----


@pytest.mark.django_db
def test_forty_eight_decks_pass_every_check(built):
    assert len(built) == 48
    for prep, prep_results, clips, deck in built:
        results = check_deck(deck, prep, clips, prep_results)
        failed = [(r.code, r.details) for r in results if r.status != PASS]
        assert not failed, (prep.lesson, prep.k, failed)


@pytest.mark.django_db
def test_example_slides_equal_examples_and_continuations(built):
    for prep, _, clips, deck in built:
        examples = [s for s in deck.slides if s.kind == "example"]
        assert len(examples) == sum(e.continuations or 1 for e in prep.examples) == len(clips)
        assert sum(s.kind == "reveal" for s in deck.slides) == len(prep.examples)


@pytest.mark.django_db
def test_last_period_has_no_example_and_carries_quiz(built):
    for prep, _, _, deck in built:
        kinds = [s.kind for s in deck.slides]
        if prep.is_last:
            assert "example" not in kinds and "objectives" not in kinds
            assert ("quiz" in kinds) == bool(prep.quiz)
        else:
            assert kinds[:3] == ["title", "recall", "objectives"]


@pytest.mark.django_db
def test_deck_is_deterministic_and_key_tracks_inputs(built):
    prep, _, clips, deck = _middle(built)
    assert build_period_deck(prep, clips) == deck
    assert deck.key.startswith(f"decks/{prep.course}/{prep.lesson}-k{prep.k}of{prep.n}-p45-")
    changed = replace(prep, homework=prep.homework[:-1])
    assert prep_digest(changed) != prep_digest(prep)
    assert period_deck_key(changed, clips) != deck.key
    other_png = fake_clips(prep, PNG + b"\x01")
    assert period_deck_key(prep, other_png) != deck.key


@pytest.mark.django_db
def test_build_rejects_bad_clips(built):
    prep, _, clips, _ = _middle(built)
    with pytest.raises(DeckError, match="خارج الحصة"):
        build_period_deck(prep, (*clips, ExampleClip(99, PNG, 10, 10)))
    with pytest.raises(DeckError, match="لا مقطع"):
        build_period_deck(prep, clips[1:])
    with pytest.raises(DeckError, match="مكرر"):
        build_period_deck(prep, (*clips, clips[0]))
    first = prep.examples[0].n
    with pytest.raises(DeckError, match="غير متصلة"):
        build_period_deck(prep, (*clips, ExampleClip(first, PNG, 10, 10, part=5)))


# ---- حالة فاشلة لكل معيار ----


def _replace_slide(deck, target, **fields):
    slides = list(deck.slides)
    i = next(i for i, s in enumerate(slides) if s.kind == target)
    slides[i] = replace(slides[i], **fields)
    return replace(deck, slides=tuple(slides))


def _drop(deck, kind):
    return replace(deck, slides=tuple(s for s in deck.slides if s.kind != kind))


@pytest.mark.django_db
def test_s1_input_fails(built):
    prep, results, clips, deck = _middle(built)
    assert s1_input(deck, prep, clips, results).status == PASS
    failed = (*results, CheckResult("T4", FAIL, ("x",)))
    assert _fails(s1_input(deck, prep, clips, failed))
    unapproved = tuple(CheckResult("T2c", FAIL) if r.code == "T2c" else r for r in results)
    assert _fails(s1_input(deck, prep, clips, unapproved))
    assert _fails(s1_input(replace(deck, key="decks/x.pptx"), prep, clips, results))
    assert _fails(s1_input(deck, prep, fake_clips(prep, PNG + b"\x02"), results))
    assert _fails(s1_input(replace(deck, k=deck.k + 1), prep, clips, results))


@pytest.mark.django_db
def test_s2_examples_fails(built):
    prep, _, clips, deck = _middle(built)
    first = prep.examples[0]
    assert _fails(s2_examples(_drop(deck, "example"), prep))
    stranger = replace(clips[0], n=99)
    assert _fails(s2_examples(_replace_slide(deck, "example", clip=stranger), prep))
    assert _fails(
        s2_examples(deck, replace(prep, examples=(replace(first, continuations=3), *prep.examples[1:])))
    )


@pytest.mark.django_db
def test_s3b_phases_fails(built):
    prep, _, _, deck = _middle(built)
    assert _fails(s3b_phases(_replace_slide(deck, "classwork", phase="direct"), prep))
    assert _fails(s3b_phases(_replace_slide(deck, "check", phase="lecture"), prep))
    assert _fails(s3b_phases(_drop(deck, "differentiation"), prep))


@pytest.mark.django_db
def test_s3_order_fails(built):
    prep, _, _, deck = _middle(built)
    slides = list(deck.slides)
    slides[0], slides[1] = slides[1], slides[0]
    assert _fails(s3_order(replace(deck, slides=tuple(slides)), prep))
    assert _fails(s3_order(_replace_slide(deck, "classwork", refs=(99,)), prep))
    assert _fails(s3_order(_replace_slide(deck, "check", kind="poll"), prep))
    assert _fails(s3_order(_drop(deck, "classwork"), prep))


@pytest.mark.django_db
def test_s4_objectives_fails(built):
    prep, _, _, deck = _middle(built)
    slide = next(s for s in deck.slides if s.kind == "objectives")
    assert _fails(s4_objectives(_replace_slide(deck, "objectives", refs=(*slide.refs, 99)), prep))
    assert _fails(s4_objectives(_replace_slide(deck, "objectives", bullets=("هدف الدرس كله",)), prep))
    assert _fails(s4_objectives(_drop(deck, "objectives"), prep))


@pytest.mark.django_db
def test_s5_pace_warns(built):
    prep, _, _, deck = _middle(built)
    extra = tuple(replace(deck.slides[-1]) for _ in range(30))
    assert _fails(s5_pace(replace(deck, slides=deck.slides + extra), prep))
    assert _fails(s5_pace(_replace_slide(deck, "recall", minutes=0), prep))
    assert not s5_pace(deck, prep).blocking


@pytest.mark.django_db
def test_s6_density_fails(built):
    _, _, _, deck = _middle(built)
    assert _fails(s6_density(_replace_slide(deck, "title", bullets=("نقطة",) * 7)))
    assert _fails(s6_density(_replace_slide(deck, "recall", bullets=("كلمة " * 40,))))
    assert _fails(s6_density(_replace_slide(deck, "recall", body_pt=20)))
    assert _fails(s6_density(_replace_slide(deck, "recall", title_pt=28)))


@pytest.mark.django_db
def test_s9_direction_fails(built):
    prep, _, _, deck = _middle(built)
    assert _fails(s9_direction(_replace_slide(deck, "recall", rtl=False)))
    assert _fails(s9_direction(_replace_slide(deck, "homework", bullets=("حلّ تمارين الكتاب: 16-19",))))
    ranged = [b for s in deck.slides for b in s.bullets if LRM in b]
    assert ranged or not any(len(c.exercises) >= 3 for c in prep.classwork)


@pytest.mark.django_db
def test_s10_accessibility_fails(built):
    prep, _, clips, deck = _middle(built)
    assert _fails(s10_accessibility(_replace_slide(deck, "recall", title=" "), prep))
    assert _fails(s10_accessibility(_replace_slide(deck, "example", alt=""), prep))
    assert _fails(s10_accessibility(_replace_slide(deck, "recall", clip=clips[0]), prep))


@pytest.mark.django_db
def test_s11_notes_warns(built):
    _, _, _, deck = _middle(built)
    assert _fails(s11_notes(_replace_slide(deck, "recall", notes=())))
    assert _fails(s11_notes(_replace_slide(deck, "classwork", bullets=("التمرين 9: DOK 2",))))
    classwork = next(s for s in deck.slides if s.kind == "classwork")
    assert _fails(s11_notes(_replace_slide(deck, "classwork", notes=classwork.notes[:2])))
    assert not s11_notes(deck).blocking


@pytest.mark.django_db
def test_s13_no_guide_text_fails(built):
    prep, _, clips, deck = _middle(built)
    assert _fails(
        s13_no_guide_text(_replace_slide(deck, "recall", bullets=("اقرأ فقرة الدليل للمعلم",)), prep)
    )
    stranger = replace(clips[0], n=99)
    assert _fails(s13_no_guide_text(_replace_slide(deck, "example", clip=stranger), prep))
    assert isinstance(deck.slides[0], PeriodSlide)
