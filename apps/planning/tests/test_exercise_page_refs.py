"""صفحات تمارين الكتاب في التحضير والعرض: التدريب الصفي والمساران والواجب بأرقامها وصفحاتها حين تُعرف."""

from __future__ import annotations

from dataclasses import replace

import pytest

from apps.curriculum.courses import GRADE10_SLUG
from apps.planning.domain.deck import build_period_deck
from apps.planning.domain.prep import prep_digest
from apps.planning.domain.prep_sheet import prep_sheet
from apps.planning.domain.strategies import load_library
from apps.planning.selectors import lesson_preps
from apps.planning.tests.test_period_deck import fake_clips


@pytest.fixture
def paged(loaded_courses):
    """حصة فيها تدريب صفي وواجب، وكل تمرين فيها على الصفحة 100 + رقمه // 10."""
    row = next(r for r in lesson_preps(GRADE10_SLUG) if r.prep.classwork and r.prep.homework)
    numbers = {x for c in row.prep.classwork for x in c.exercises} | set(row.prep.homework)
    return row, replace(row.prep, exercise_pages={x: 100 + x // 10 for x in sorted(numbers)})


def test_empty_pages_keep_digest_and_text(paged):
    row, prep = paged
    assert row.prep.exercise_pages == {}  # الفهرس المودَع بلا صفحات تمارين بعد
    assert prep_digest(replace(prep, exercise_pages={})) == prep_digest(row.prep)
    assert prep_digest(prep) != prep_digest(row.prep)


def test_prep_sheet_shows_exercise_pages(paged):
    row, prep = paged
    library = {s.slug: s for s in load_library()}
    sheet = prep_sheet(
        prep, row.checks, library, lesson_title="", week=1, number=1, year="2026-2027", semester=1, grade=""
    )
    work = prep.classwork[0]
    assert f"(ص {100 + work.exercises[0] // 10})" in next(
        o.check_activity for o in sheet.objectives if o.example == work.example
    )
    assert f"(ص {100 + prep.homework[0] // 10})" in sheet.homework


def test_deck_classwork_and_homework_show_exercise_pages(paged):
    _, prep = paged
    deck = build_period_deck(prep, fake_clips(prep))
    slides = {s.kind: s for s in deck.slides}
    work = prep.classwork[0]
    classwork = next(s for s in deck.slides if s.kind == "classwork" and s.refs == (work.example,))
    assert f"(ص {100 + work.exercises[0] // 10})" in classwork.bullets[0]
    assert f"(ص {100 + prep.homework[0] // 10})" in slides["homework"].bullets[0]
