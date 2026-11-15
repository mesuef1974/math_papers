import pytest

from tools.extraction.fields import field, worst
from tools.extraction.text import chain_max, norm, parse_numbers, squash, strip_al


def test_norm_folds_arabic_and_digits():
    assert norm("الدَّالّةُ ١٢") == "الداله 12"
    assert norm("أإآ ى ة") == "ااا ي ه"


def test_squash_removes_all_whitespace():
    assert squash("ما  ستتعلّمه\n") == "ماستتعلمه"


def test_strip_al_only_long_words():
    assert strip_al("التحليل") == "تحليل"
    assert strip_al("الف") == "الف"


def test_parse_numbers_ranges_and_noise():
    assert parse_numbers("1-3، 7") == [1, 2, 3, 7]
    assert parse_numbers("١٥–١٧") == [15, 16, 17]
    assert parse_numbers("9-3, 120, x") == []


def test_chain_max_stops_at_gap():
    assert chain_max({1, 2, 3, 4, 40}, 5) == 4
    assert chain_max({7, 8}, 5) == 0
    assert chain_max([], 5) == 0


def test_field_validates_source_and_status():
    f = field([1], "guide", "ok", note="x")
    assert f == {"value": [1], "source": "guide", "status": "ok", "note": "x"}
    with pytest.raises(ValueError):
        field(1, "web", "ok")
    with pytest.raises(ValueError):
        field(1, "guide", "fine")


def test_worst_status():
    assert worst(["ok", "review", "ok"]) == "review"
    assert worst(["ok", "missing"]) == "missing"
    assert worst([]) == "missing"
