"""قسمة المقطع الطويل عند فراغ أبيض: مواضع القص، والقص نفسه، وأجزاؤه في العرض."""

import pytest

from apps.planning.domain.deck import DeckError, ExampleClip, content_digest
from apps.planning.example_clips import (
    MAX_ASPECT,
    find_cuts,
    merge_groups,
    merge_short_continuations,
    piece_sizes,
)
from apps.planning.png_stack import _encode, rgb_rows, slice_png

WIDTH = 200
INK, BLANK = b"\x00" + b"\x00" * (3 * WIDTH), b"\x00" + b"\xff" * (3 * WIDTH)


def png(*blocks: tuple[int, bool]) -> bytes:
    return _encode(WIDTH, [line for height, ink in blocks for line in [INK if ink else BLANK] * height])


TALL = png((150, True), (10, False), (150, True))  # 310 على 200: أطول من الحد


def test_short_clip_is_not_cut():
    assert find_cuts(png((200, True))) == ()


def test_tall_clip_is_cut_in_the_white_gap_and_pieces_fit():
    cuts = find_cuts(TALL)
    assert cuts == (155,)
    assert all(h <= MAX_ASPECT * w for w, h in piece_sizes(WIDTH, 310, cuts))
    pieces = slice_png(TALL, cuts)
    assert [(w, h) for _, w, h in pieces] == piece_sizes(WIDTH, 310, cuts)
    assert [row for data, _, _ in pieces for row in rgb_rows(data)[1]] == rgb_rows(TALL)[1]


def test_tall_clip_without_a_gap_is_reported_not_cut_through_ink():
    assert find_cuts(png((310, True))) is None


def test_bad_cuts_are_rejected():
    with pytest.raises(DeckError):
        slice_png(TALL, (400,))


def test_deck_clips_are_split_and_renumbered_with_the_same_count_as_the_prep():
    source = (ExampleClip(n=2, png=TALL, width_px=WIDTH, height_px=310, cuts=(155,)),)
    shown = merge_short_continuations(source)
    assert [(c.part, c.height_px) for c in shown] == [(1, 155), (2, 155)]
    assert len(shown) == len(merge_groups(piece_sizes(WIDTH, 310, (155,))))


def test_cuts_change_the_deck_digest():
    assert content_digest("a", ()) == content_digest("a", None) == "a"
    assert content_digest("a", (155,)) != "a"
