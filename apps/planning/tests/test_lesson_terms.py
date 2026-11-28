"""مصطلحات الدرس في التحضير والعرض (قرار المالك 2026-11-28)."""

import pytest

from apps.knowledge.selectors import lesson_terms
from apps.planning.domain.deck import build_period_deck
from apps.planning.selectors import lesson_preps

from .test_period_deck import fake_clips


@pytest.mark.parametrize("course", ["g10-s1", "g12-sci-s1"])
def test_lesson_terms_reach_every_period_deck(course, loaded_courses):
    terms = lesson_terms(course)
    assert terms
    for row in lesson_preps(course):
        prep = row.prep
        assert prep.terms == terms.get(prep.lesson, ())
        deck = build_period_deck(prep, fake_clips(prep))
        shown = [b for s in deck.slides if s.kind == "terms" for b in s.bullets]
        assert len(shown) == len(prep.terms), (prep.lesson, prep.k)
        assert all(ar in bullet for (ar, _), bullet in zip(prep.terms, shown, strict=True))


def test_every_grade10_lesson_has_terms(loaded_courses):
    terms = lesson_terms("g10-s1")
    assert {row.prep.lesson for row in lesson_preps("g10-s1")} <= set(terms)
