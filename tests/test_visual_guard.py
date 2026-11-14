"""مقارنة الحارس البصري: دالة صرفة بلا متصفح؛ التشغيل الحقيقي بمتصفح يدوي (scripts/visual_guard.py)."""

from scripts.visual_guard import compare_boxes


def boxes(**selectors):
    return {name: list(items) for name, items in selectors.items()}


def test_identical_layout_passes():
    layout = boxes(**{".question": [(688.0, 300.0)], ".part": [(688.0, 120.0), (688.0, 90.5)]})
    assert compare_boxes(layout, layout) == []


def test_difference_within_tolerance_passes():
    screen = boxes(**{".part": [(688.0, 120.0)]})
    printed = boxes(**{".part": [(687.9, 120.9)]})
    assert compare_boxes(screen, printed, tolerance=1.0) == []


def test_extra_wrapped_line_is_reported_with_element_and_sizes():
    screen = boxes(**{".part": [(688.0, 120.0), (688.0, 90.0)]})
    printed = boxes(**{".part": [(688.0, 120.0), (688.0, 122.0)]})
    problems = compare_boxes(screen, printed)
    assert len(problems) == 1
    assert (
        ".part رقم 2" in problems[0]
        and "الارتفاع" in problems[0]
        and "90.0" in problems[0]
        and "122.0" in problems[0]
    )


def test_width_drift_and_count_mismatch_are_reported():
    screen = boxes(**{".question": [(688.0, 300.0)], ".part": [(688.0, 100.0), (688.0, 80.0)]})
    printed = boxes(**{".question": [(650.0, 300.0)], ".part": [(688.0, 100.0)]})
    problems = compare_boxes(screen, printed)
    assert any(".question رقم 1" in p and "العرض" in p for p in problems)
    assert any(p.startswith(".part: العدد 2") and "1 في الطباعة" in p for p in problems)


def test_sheet_width_itself_is_not_compared():
    """الشاشة 210مم والطباعة 182مم بالتصميم؛ المقارنة على ما داخل الورقة لا على إطارها."""
    screen = boxes(**{".sheet": [(794.0, 0.0)], ".part": [(688.0, 100.0)]})
    printed = boxes(**{".sheet": [(688.0, 0.0)], ".part": [(688.0, 100.0)]})
    assert compare_boxes(screen, printed) == []


def test_selector_missing_on_one_side_is_a_mismatch():
    problems = compare_boxes(boxes(**{".part": [(688.0, 100.0)]}), boxes())
    assert problems and ".part: العدد 1" in problems[0]
