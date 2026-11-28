"""لا تقييم بنائي ولا بطاقة خروج بعبارة بلا سؤال محدد (قرار المالك 2026-11-28): المقرران."""

import pytest

from apps.planning.domain.check_items import book_exercise, period_items, split_check_questions
from apps.planning.domain.deck import PERIOD_TEXT, build_period_deck
from apps.planning.selectors import lesson_preps

from .test_period_deck import fake_clips

PHRASE = PERIOD_TEXT["skill_question"].split("{")[0].strip()


@pytest.mark.parametrize("course", ["g10-s1", "g12-sci-s1"])
def test_every_formative_and_exit_slide_asks_a_concrete_question(course, loaded_courses):
    rows = lesson_preps(course)
    assert rows
    for row in rows:
        prep, items = row.prep, period_items(row.prep)
        where = (course, prep.lesson, prep.k)
        _, as_open = split_check_questions(prep, items)
        assert all(n in items.open or book_exercise(prep, n) for n in as_open), where
        deck = build_period_deck(prep, fake_clips(prep))
        for slide in deck.slides:
            if slide.kind in ("check", "exit"):
                assert not any(PHRASE in b for b in slide.bullets), (where, slide.bullets)
                assert any("الإجابة" in n or "إجابته" in n for n in slide.notes), (where, slide.notes)
