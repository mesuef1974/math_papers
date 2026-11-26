"""عزل المدى الرقمي لا يقطع تعبيرًا رياضيًا. نظيره frontend/src/utils/bidi.test.ts."""

import pytest

from apps.papers.domain.bidi import LRM, NB_HYPHEN, RLM, isolate_number_ranges


@pytest.mark.parametrize(
    "text",
    [
        "(8 - 4 x)",
        "x² - 6 x + 8",
        "2 - 3x",
        "x - 8 - 4",
        "y = 2 - 3",
        "(5 - 2)²",
        "2(3 - 1)",
        "3 - 1.5x",
        "-2 - 3",
        "x^2 - 6",
        f"{LRM}8 - 4{RLM}",
    ],
)
def test_no_isolation_inside_a_math_expression(text):
    assert isolate_number_ranges(text) == text


@pytest.mark.parametrize(
    ("text", "number_range"),
    [
        ("2026-2027", "2026-2027"),
        ("الصفحات 10 - 12", "10 - 12"),
        ("العام (2026-2027)", "2026-2027"),
        ("العاشر، 2026-2027", "2026-2027"),
        ("أ) 2-3", "2-3"),
        ("DOK 2-3", "2-3"),
    ],
)
def test_number_range_in_arabic_text_stays_isolated(text, number_range):
    wrapped = f"{LRM}{number_range.replace('-', NB_HYPHEN)}{RLM}"
    assert isolate_number_ranges(text) == text.replace(number_range, wrapped)


def test_isolating_twice_changes_nothing():
    once = isolate_number_ranges("العاشر، 2026-2027")
    assert isolate_number_ranges(f"{once} – 10") == f"{once} – 10"
