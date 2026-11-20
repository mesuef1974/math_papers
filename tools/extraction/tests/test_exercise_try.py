"""مرحلة exercise_try: سطر «حاول أن تحل التمرين N» في صفحات الأمثلة، بصناديق مصطنعة وصفحات مركّبة وقارئ وهمي، لا نص دليل."""

import json
import re

import pytest

from tools.extraction import exercise_try, ocr
from tools.extraction.__main__ import main, run_stage

from .conftest import TOY_PAGES, make_book

Image = pytest.importorskip("PIL.Image")
ImageDraw = pytest.importorskip("PIL.ImageDraw")

ID_PATTERN = r"(?<![\d.a-z])(\d{1,2})\.(\d{1,2})(?![\d.])"
TRY = "حاول أن تحل التمرين"
H = 36
CFG = exercise_try.DEFAULTS


def _label(y):
    return ("مثال", [600, y, 680, y + H])


def _try(y, x0=300):
    return (TRY, [x0, y, 620, y + H])


def _page(numbers):
    """صفحة يحمل فيها الطرف الأيسر من كل سطر «حاول أن تحل» (x0، y) رقمه رمادًا بدرجة 4×الرقم، ويقرؤه القارئ الوهمي."""
    image = Image.new("RGB", (1000, 1400), "white")
    draw = ImageDraw.Draw(image)
    for (x0, y), n in numbers.items():
        draw.rectangle([x0, y, x0 + H, y + H - 1], fill=(4 * n,) * 3)
    return image


def fake_ocr(crop):
    """يقرأ رقم المربع الرمادي في المقطع: يصح فقط إن قُصّ الطرف الأيسر من السطر لا السطر كله (فيه بياض يميزه)."""
    gray = crop.convert("L")
    values = [v for v in gray.tobytes() if v < 250]
    if not values or len(values) < 0.5 * gray.width * gray.height:
        return "حاول أن تحل التمرين", 0.97  # السطر كله: التعرّف يُسقط الرقم
    n = round(min(values) / 4)
    return (str(n), 0.99) if n else ("", 0.0)


# ───── الدوال النقية ─────
@pytest.mark.parametrize(
    "text, cap, want",
    [
        ("33", 60, [33]),
        ("التمرين 12 و13", 60, [12, 13]),
        ("12-14", 60, [12, 13, 14]),
        ("12-40", 60, [12, 40]),  # مدى أطول من RANGE ليس مدى
        ("٢٨", 60, [28]),
        ("73", 60, []),
        ("", 60, []),
    ],
)
def test_exercise_numbers(text, cap, want):
    assert exercise_try.exercise_numbers(text, cap) == want


def test_events_are_label_and_try_lines_from_the_top():
    boxes = [
        _try(500),
        ("شرح", [100, 50, 600, 80]),
        _label(100),
        ("مثال 3 أخرى في النص", [100, 300, 600, 330]),
    ]
    assert [(kind, box[1]) for kind, box, _ in exercise_try.events(boxes, CFG["marker"])] == [
        ("label", 100),
        ("try", 500),
    ]


def test_read_try_reads_the_left_end_of_the_line_box():
    image = _page({(300, 200): 33})
    assert exercise_try.read_try(image, [300, 200, 620, 200 + H], TRY, fake_ocr, 60, CFG) == ([[33]], True)


def test_read_try_votes_across_crop_widths():
    """القصّ الأضيق يبتر والأعرض يضيف خانة: القراءة ما تكرر، والبقية بدائل مرتبة."""
    reads = iter([("4", 0.99), ("4", 0.8), ("49", 0.9)])
    got = exercise_try.read_try(_page({}), [300, 200, 620, 236], TRY, lambda crop: next(reads), 60, CFG)
    assert got == ([[4], [49]], True)


def test_read_try_falls_back_to_the_box_text_on_low_confidence_or_no_image():
    image = _page({(300, 200): 33})
    low = {**CFG, "min_score": 1.5}
    assert exercise_try.read_try(image, [300, 200, 620, 236], f"{TRY} 9", fake_ocr, 60, low) == ([[9]], False)
    assert exercise_try.read_try(None, [300, 200, 620, 236], f"{TRY} 9", fake_ocr, 60, CFG) == ([[9]], False)
    assert exercise_try.read_try(None, [300, 200, 620, 236], TRY, fake_ocr, 60, CFG) == ([], False)


def _events(*items):
    """أحداث صفحة: ("label"، []) أو ("try"، [أرقام] أو [[قراءة]، [بديل]...])."""
    out = []
    for i, (kind, numbers) in enumerate(items):
        reads = numbers if numbers and isinstance(numbers[0], list) else ([numbers] if numbers else [])
        out.append((kind, [0, i, 0, i], reads))
    return out


def test_link_counts_examples_from_the_lines_themselves():
    pages = {
        3: _events(("label", []), ("try", [4]), ("label", []), ("try", [9])),
        4: _events(("label", []), ("try", [15])),
    }
    got = exercise_try.link(pages)
    assert got["links"] == [
        {"example": 1, "exercises": [4], "pages": [3]},
        {"example": 2, "exercises": [9], "pages": [3]},
        {"example": 3, "exercises": [15], "pages": [4]},
    ]
    assert (got["lines"], got["unread"], got["labels"], got["opened"], got["monotone"]) == (3, 0, 3, 0, True)


def test_a_try_line_after_a_taken_one_opens_the_next_example():
    # فات OCR سطر «مثال» للمثال 2 (وفي أول الدرس للمثال 1): السطر الثاني للمثال 2 لا يُضم إلى المثال 1
    pages = {3: _events(("try", [4])), 5: _events(("try", [9]), ("label", []), ("try", [12]))}
    got = exercise_try.link(pages)
    assert [row["exercises"] for row in got["links"]] == [[4], [9], [12]]
    assert (got["labels"], got["opened"]) == (1, 2)


def test_an_unread_line_does_not_take_the_place_of_its_example_line():
    pages = {
        3: _events(("label", []), ("try", []), ("try", [9]), ("label", []), ("label", []), ("try", [20]))
    }
    got = exercise_try.link(pages)
    assert [row["exercises"] for row in got["links"]] == [[9], [], [20]]
    assert (got["unread"], got["lines"], got["opened"]) == (1, 3, 0)


def test_trailing_labels_without_a_line_are_dropped_and_backward_numbers_break_monotony():
    pages = {3: _events(("label", []), ("try", [30]), ("label", []), ("try", [9])), 9: _events(("label", []))}
    got = exercise_try.link(pages)
    assert [row["example"] for row in got["links"]] == [1, 2]
    assert got["monotone"] is False


def test_a_number_against_its_neighbours_takes_an_alternative_read_that_fits():
    pages = {
        3: _events(
            ("label", []),
            ("try", [3]),
            ("label", []),
            ("try", [[59], [5]]),
            ("label", []),
            ("try", [[7], [70]]),
        )
    }
    got = exercise_try.link(pages)
    assert [row["exercises"] for row in got["links"]] == [[3], [5], [7]]
    assert (got["repaired"], got["monotone"]) == (1, True)
    # جار لاحق مخطئ (4 لا 46) يحجب بديل سابقه (30) حتى يُصلح هو: الإصلاح حتى الثبات
    chain = exercise_try.link(
        {
            3: _events(
                ("label", []),
                ("try", [28]),
                ("label", []),
                ("try", [[3], [30]]),
                ("label", []),
                ("try", [37]),
                ("label", []),
                ("try", [[4], [46]]),
            )
        }
    )
    assert [row["exercises"] for row in chain["links"]] == [[28], [30], [37], [46]]
    assert (chain["repaired"], chain["monotone"]) == (2, True)
    # لا بديل بين جاريه (9 و12): يبقى المختار ويبقى التزايد مكسورًا للمراجعة
    stuck = exercise_try.link(
        {
            3: _events(
                ("label", []), ("try", [9]), ("label", []), ("try", [[2], [29]]), ("label", []), ("try", [12])
            )
        }
    )
    assert [row["exercises"] for row in stuck["links"]] == [[9], [2], [12]]
    assert (stuck["repaired"], stuck["monotone"]) == (0, False)


# ───── المرحلة وexercise_links ─────
def _book(tmp_path, monkeypatch):
    """الدرس 1.1: مثالان في الصفحتين 3 و4 بسطري «حاول أن تحل» 2 و3؛ الدرس 1.2 بلا سطر فيبقى على التجاور."""
    book = make_book(tmp_path, TOY_PAGES, dirs={"vision": "hybrid"}, layout={"id_pattern": ID_PATTERN})
    for name in ("hybrid", "render", "boxes"):
        (tmp_path / name).mkdir()
    for page, n in ((3, 2), (4, 3)):
        _page({(300, 400): n}).save(tmp_path / "render" / f"{page:04d}.png")
        boxes = [_label(100), _try(400)]
        (tmp_path / "boxes" / f"{page:04d}.json").write_text(
            json.dumps([[t, b] for t, b in boxes], ensure_ascii=False), encoding="utf-8"
        )
    seen = {
        3: {"examples": [1], "exercises": []},
        4: {"examples": [2], "exercises": []},
        5: {"examples": [1, 2], "exercises": [1, 2, 3]},
        7: {"examples": [1], "exercises": []},
        8: {"examples": [1], "exercises": [1, 2]},
    }
    for page, data in seen.items():
        (tmp_path / "hybrid" / f"{page:04d}.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(ocr, "read_scored", fake_ocr)  # لا PaddleOCR في الاختبار
    return book


def _lessons(book, name):
    return json.loads((book.out / f"{name}.json").read_text(encoding="utf-8"))["lessons"]


def test_stage_writes_numbers_only_and_prints_counts(tmp_path, monkeypatch, capsys):
    book = _book(tmp_path, monkeypatch)
    assert main([str(tmp_path), "exercise_try"]) == 0
    out = capsys.readouterr().out
    assert '"linked_examples": 2' in out and '"lines": 2' in out and '"unread": 0' in out
    first, second = (_lessons(book, "exercise_try")[k] for k in ("1.1", "1.2"))
    assert (first["source"], first["status"], first["monotone"], first["opened"]) == (
        "derived",
        "review",
        True,
        0,
    )
    assert first["value"] == [
        {"example": 1, "exercises": [2], "pages": [3]},
        {"example": 2, "exercises": [3], "pages": [4]},
    ]
    assert (second["status"], second["lines"]) == ("missing", 0)
    raw = (book.out / "exercise_try.json").read_text(encoding="utf-8")
    assert not re.search("[ء-ي]", raw)  # أرقام وحدها، بلا نص
    assert run_stage(book, "exercise_try") is False  # مختومة


def test_links_take_try_lessons_first_and_fall_back_to_adjacency(tmp_path, monkeypatch):
    book = _book(tmp_path, monkeypatch)
    assert main([str(tmp_path), "exercise_try"]) == 0
    assert main([str(tmp_path), "exercise_links"]) == 0
    first, second = (_lessons(book, "exercise_links")[k] for k in ("1.1", "1.2"))
    assert (first["method"], first["status"]) == ("try", "review")
    assert [row["exercises"] for row in first["value"]] == [[2], [3]]
    assert second["method"] == "adjacency"
    assert second["value"] == [{"example": 1, "exercises": [1, 2], "pages": [8]}]
