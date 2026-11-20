"""مرحلة exercise_badges: صفحات مركّبة (مربعات ملونة فيها أشرطة بيضاء مكان الرقم) وصناديق مصطنعة وOCR وهمي، لا نص دليل."""

import json
import re

import pytest

from tools.extraction import exercise_badges, ocr
from tools.extraction.__main__ import main, run_stage

from .conftest import TOY_PAGES, make_book

Image = pytest.importorskip("PIL.Image")
ImageDraw = pytest.importorskip("PIL.ImageDraw")

ID_PATTERN = r"(?<![\d.a-z])(\d{1,2})\.(\d{1,2})(?![\d.])"
COLOR = (200, 30, 60)
SIDE = 40
# الشارة المركّبة تحمل أشرطة بيضاء بدل رقم، والقارئ الوهمي يعدّها: 4 أشرطة شارة برقمين، و5 شارة لا تُقرأ
TEXT = {1: "1", 2: "2", 3: "3", 4: "1 و2", 5: "؟"}


def _badge(draw, x, y, bars, shape="rectangle"):
    getattr(draw, shape)([x, y, x + SIDE - 1, y + SIDE - 1], fill=COLOR)
    for i in range(bars):
        draw.rectangle([x + 5 + 7 * i, y + 10, x + 7 + 7 * i, y + 29], fill="white")


def _page(badges=(), anchors=()):
    """صورة صفحة فيها شارات (x، y، أشرطة) وصناديق أرقام تدريبات (رقم، الحافة اليمنى، y)."""
    image = Image.new("RGB", (1000, 1400), "white")
    draw = ImageDraw.Draw(image)
    for x, y, bars in badges:
        _badge(draw, x, y, bars)
    return image, [(f"{n}.", [right - 20, y, right, y + 24]) for n, right, y in anchors]


def fake_ocr(crop):
    """يعدّ الأشرطة الداكنة في السطر الأوسط: يصح فقط إن عُكست الشارة إلى داكن على فاتح."""
    gray = crop.convert("L")
    row = gray.crop((0, gray.height // 2, gray.width, gray.height // 2 + 1)).tobytes()
    dark = [v < 128 for v in row]
    bars = sum(now and not before for before, now in zip([False, *dark], dark, strict=False))
    return TEXT.get(bars, "")


def _link(*pages, accepted=(1, 2), first=5):
    scans = {
        first + i: exercise_badges.scan(image, boxes, fake_ocr, exercise_badges.DEFAULTS, 9, 60)
        for i, (image, boxes) in enumerate(pages)
    }
    return exercise_badges.link(scans, set(accepted), 5)


# ───── الدوال النقية ─────
def test_find_badges_wants_a_colored_box_of_badge_size_with_an_enclosed_light_digit():
    image = Image.new("RGB", (1000, 1400), "white")
    draw = ImageDraw.Draw(image)
    _badge(draw, 900, 100, 1)
    _badge(draw, 700, 100, 2, shape="ellipse")  # دائرة: زواياها البيضاء خارجها لا رقم فيها
    _badge(draw, 500, 100, 0)  # مربع ملون بلا رقم
    _badge(draw, 300, 100, 0, shape="ellipse")  # دائرة بلا رقم
    draw.rectangle([100, 300, 399, 599], fill=COLOR)  # صورة ملونة أكبر من شارة
    draw.rectangle([200, 400, 220, 420], fill="white")
    draw.rectangle([600, 300, 604, 304], fill=COLOR)  # نقطة أصغر من شارة
    draw.rectangle([800, 300, 839, 339], outline=COLOR)  # إطار رفيع حول بياض
    draw.rectangle([800, 500, 839, 539], fill=(90, 90, 90))  # رمادي غير مشبع
    assert exercise_badges.find_badges(image) == [[700, 100, 740, 140], [900, 100, 940, 140]]


def test_find_badges_by_configured_color_ignores_other_colors():
    image = Image.new("RGB", (1000, 1400), "white")
    draw = ImageDraw.Draw(image)
    _badge(draw, 900, 100, 1)
    draw.rectangle([700, 100, 739, 139], fill=(20, 90, 200))
    draw.rectangle([710, 110, 714, 129], fill="white")
    assert len(exercise_badges.find_badges(image)) == 2
    assert exercise_badges.find_badges(image, {"color": list(COLOR), "tolerance": 30}) == [
        [900, 100, 940, 140]
    ]


def test_read_badge_hands_ocr_a_dark_on_light_crop_four_times_larger():
    image, _ = _page(badges=[(900, 100, 3)])
    seen = []

    def spy(crop):
        seen.append(crop)
        return fake_ocr(crop)

    box = exercise_badges.find_badges(image)[0]
    assert exercise_badges.read_badge(image, box, spy) == {
        "box": [900, 100, 940, 140],
        "examples": [3],
        "unreadable": False,
    }
    crop = seen[0]
    assert crop.width >= SIDE * 4 and crop.height >= SIDE * 4
    assert crop.getpixel((0, 0)) == (255, 255, 255)  # لون الشارة صار فاتحًا
    middle_bar = (crop.width - SIDE * 4) // 2 + 13 * 4 + 2  # الشريط الثاني عند 12 إلى 14 من حافة الشارة
    assert max(crop.getpixel((middle_bar, crop.height // 2))) < 60  # والشريط الأبيض صار داكنًا


@pytest.mark.parametrize(
    ("text", "ceiling", "want"),
    [
        ("3", 9, [3]),
        ("1 و2", 9, [1, 2]),
        ("٢", 9, [2]),
        ("12", 9, [1, 2]),  # رقمان متلاصقان في شارة واحدة
        ("12", 12, [12]),
        ("0", 9, []),
        ("؟", 9, []),
        ("", 9, []),
    ],
)
def test_example_numbers(text, ceiling, want):
    assert exercise_badges.example_numbers(text, ceiling) == want


def test_exercise_anchors_are_boxes_holding_one_exercise_number():
    box = [10, 10, 30, 30]
    texts = ["3.", "12)", "7", "٤", "61", "0", "123", "3 أ", "1.2", "س"]
    got = exercise_badges.exercise_anchors([(t, box) for t in texts], 60)
    assert [a["n"] for a in got] == [3, 12, 7, 4]
    assert got[0]["box"] == box


def test_assign_reads_columns_from_the_right_then_down():
    badges = [{"box": [900, 100, 940, 140], "examples": [1]}, {"box": [400, 400, 440, 440], "examples": [2]}]
    anchors = [
        {"n": n, "box": [right - 20, y, right, y + 24]}
        for n, right, y in [(4, 450, 300), (2, 950, 600), (5, 450, 500), (1, 950, 200), (3, 450, 150)]
    ]
    assert exercise_badges.assign(badges, anchors, 1000) == {
        "links": {1: {"exercises": [1, 2, 3, 4], "pages": [0]}, 2: {"exercises": [5], "pages": [0]}},
        "unlinked": [],
    }


# ───── الحالات السبع ─────
def test_one_badge_takes_the_exercises_after_it():
    got = _link(_page(badges=[(900, 100, 1)], anchors=[(1, 880, 160), (2, 880, 260), (3, 880, 360)]))
    assert got["links"] == [
        {"example": 1, "exercises": [1, 2, 3], "pages": [5]},
        {"example": 2, "exercises": [], "pages": []},
    ]
    assert got["unlinked"] == []
    assert got["pages"] == [{"page": 5, "badges": 1, "unreadable": 0, "exercises": 3}]


def test_two_columns_are_read_right_column_first():
    # التدريب 3 في العمود الأيسر أعلى من 2 في الأيمن، وشارة المثال 2 في منتصف العمود الأيسر
    got = _link(
        _page(
            badges=[(900, 100, 1), (400, 400, 2)],
            anchors=[(1, 950, 200), (2, 950, 600), (3, 450, 150), (4, 450, 300), (5, 450, 500)],
        )
    )
    assert got["links"] == [
        {"example": 1, "exercises": [1, 2, 3, 4], "pages": [5]},
        {"example": 2, "exercises": [5], "pages": [5]},
    ]


def test_a_badge_extends_to_the_next_page_until_a_new_badge():
    got = _link(
        _page(badges=[(900, 100, 1)], anchors=[(1, 880, 200), (2, 880, 300)]),
        _page(badges=[(900, 200, 2)], anchors=[(3, 880, 100), (4, 880, 300)]),
    )
    assert got["links"] == [
        {"example": 1, "exercises": [1, 2, 3], "pages": [5, 6]},
        {"example": 2, "exercises": [4], "pages": [6]},
    ]


def test_a_badge_with_two_numbers_links_both_examples():
    got = _link(_page(badges=[(900, 100, 4)], anchors=[(1, 880, 200), (2, 880, 300)]))
    assert got["links"] == [
        {"example": 1, "exercises": [1, 2], "pages": [5]},
        {"example": 2, "exercises": [1, 2], "pages": [5]},
    ]


def test_an_unreadable_badge_is_counted_and_its_exercises_stay_unlinked():
    got = _link(_page(badges=[(900, 100, 1), (900, 300, 5)], anchors=[(1, 880, 200), (2, 880, 400)]))
    assert got["links"][0] == {"example": 1, "exercises": [1], "pages": [5]}
    assert got["unlinked"] == [2]  # لا يرث شارة المثال 1: بينهما شارة لم تُقرأ
    assert got["pages"] == [{"page": 5, "badges": 2, "unreadable": 1, "exercises": 2}]


def test_exercises_before_the_first_badge_are_unlinked():
    got = _link(_page(badges=[(900, 300, 1)], anchors=[(1, 880, 100), (2, 880, 200), (3, 880, 400)]))
    assert got["links"][0] == {"example": 1, "exercises": [3], "pages": [5]}
    assert got["unlinked"] == [1, 2]


def test_a_badge_for_an_unknown_example_is_rejected():
    got = _link(_page(badges=[(900, 100, 3)], anchors=[(1, 880, 200)]))
    assert got["rejected"] == [3] and got["unlinked"] == [1]
    assert all(not row["exercises"] for row in got["links"])


def _book(tmp_path, monkeypatch):
    """الدرس 1.1 صفحة تمارينه (5) بشارتين، والدرس 1.2 صفحته (8) بلا شارات؛ والرؤية ترى أرقام الصفحتين."""
    book = make_book(tmp_path, TOY_PAGES, dirs={"vision": "hybrid"}, layout={"id_pattern": ID_PATTERN})
    for name in ("hybrid", "render", "boxes"):
        (tmp_path / name).mkdir()
    pages = {
        5: _page(
            badges=[(900, 100, 1), (900, 400, 2)], anchors=[(1, 880, 200), (2, 880, 300), (3, 880, 500)]
        ),
        8: _page(anchors=[(1, 880, 200), (2, 880, 300)]),
    }
    for page, (image, boxes) in pages.items():
        image.save(tmp_path / "render" / f"{page:04d}.png")
        (tmp_path / "boxes" / f"{page:04d}.json").write_text(json.dumps(boxes), encoding="utf-8")
    seen = {
        3: {"examples": [1], "exercises": []},
        4: {"examples": [2], "exercises": []},
        5: {"examples": [1, 2], "exercises": [1, 2, 3]},
        7: {"examples": [1], "exercises": []},
        8: {"examples": [1], "exercises": [1, 2]},
    }
    for page, data in seen.items():
        (tmp_path / "hybrid" / f"{page:04d}.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(ocr, "read_crop", fake_ocr)  # لا PaddleOCR في الاختبار
    return book


def _lessons(book, name):
    return json.loads((book.out / f"{name}.json").read_text(encoding="utf-8"))["lessons"]


def test_stage_writes_numbers_only_and_prints_counts(tmp_path, monkeypatch, capsys):
    book = _book(tmp_path, monkeypatch)
    assert main([str(tmp_path), "exercise_badges"]) == 0
    out = capsys.readouterr().out
    assert '"lessons": 2' in out and '"linked_examples": 2' in out
    assert '"badges": 2' in out and '"unreadable": 0' in out
    first, second = (_lessons(book, "exercise_badges")[k] for k in ("1.1", "1.2"))
    assert (first["source"], first["status"]) == ("derived", "review")
    assert first["value"] == [
        {"example": 1, "exercises": [1, 2], "pages": [5]},
        {"example": 2, "exercises": [3], "pages": [5]},
    ]
    assert first["pages"] == [{"page": 5, "badges": 2, "unreadable": 0, "exercises": 3}]
    assert (second["status"], second["badges"], second["unlinked"]) == ("missing", 0, [1, 2])
    raw = (book.out / "exercise_badges.json").read_text(encoding="utf-8")
    assert not re.search("[ء-ي]", raw)  # أرقام وحدها، بلا نص
    assert run_stage(book, "exercise_badges") is False  # مختومة


def test_links_take_badge_lessons_and_fall_back_to_adjacency_without_badges(tmp_path, monkeypatch):
    book = _book(tmp_path, monkeypatch)
    assert main([str(tmp_path), "exercise_links"]) == 0  # قبل الشارات: التجاور يعطي المثالين التدريبات نفسها
    before = _lessons(book, "exercise_links")["1.1"]
    assert before["method"] == "adjacency"
    assert [row["exercises"] for row in before["value"]] == [[1, 2, 3], [1, 2, 3]]

    assert main([str(tmp_path), "exercise_badges"]) == 0
    assert main([str(tmp_path), "exercise_links"]) == 0  # ناتج الشارات مدخل ختمها فتُعاد
    lessons = _lessons(book, "exercise_links")
    first, second = lessons["1.1"], lessons["1.2"]
    assert (first["method"], first["source"], first["status"]) == ("badges", "derived", "review")
    assert first["value"] == [
        {"example": 1, "exercises": [1, 2], "pages": [5]},
        {"example": 2, "exercises": [3], "pages": [5]},
    ]
    # الدرس بلا شارات يبقى على قاعدة التجاور
    assert second["method"] == "adjacency"
    assert second["value"] == [{"example": 1, "exercises": [1, 2], "pages": [8]}]


# ───── إصلاحات المراجعة ─────
def test_badges_outside_the_exercise_area_are_ignored():
    # دائرة رقم الصفحة أسفلها، وشارة في الهامش الأيمن، وزخرفة في الترويسة: لا تقطع شارة المثال 1 ولا تُحسب إحالة
    got = _link(
        _page(
            badges=[(900, 100, 1), (960, 250, 2), (500, 10, 2), (900, 1300, 2)],
            anchors=[(1, 880, 200), (2, 880, 300), (3, 880, 400)],
        )
    )
    assert got["links"] == [
        {"example": 1, "exercises": [1, 2, 3], "pages": [5]},
        {"example": 2, "exercises": [], "pages": []},
    ]


def test_a_page_without_exercise_numbers_has_no_badges():
    got = _link(
        _page(badges=[(900, 100, 1)], anchors=[(1, 880, 200)]),
        _page(badges=[(900, 1300, 2)]),  # صفحة بلا تدريبات: شارتها لا تنتقل إلى ما بعدها
        _page(anchors=[(2, 880, 200)]),
    )
    assert got["links"][0] == {"example": 1, "exercises": [1, 2], "pages": [5, 7]}


def test_a_lone_number_does_not_make_a_column():
    # «7» رقم منفرد بين العمودين (في نص تدريب أو على حافة العمود الأيمن): لا يصير عمودًا يزيح ترتيب الأعمدة
    badges = [{"box": [900, 100, 940, 140], "examples": [1]}, {"box": [400, 400, 440, 440], "examples": [2]}]
    anchors = [
        {"n": n, "box": [right - 20, y, right, y + 24]}
        for n, right, y in [
            (1, 950, 200),
            (2, 950, 600),
            (7, 700, 450),
            (3, 450, 150),
            (4, 450, 300),
            (5, 450, 500),
        ]
    ]
    assert exercise_badges._columns(anchors, 1000, exercise_badges.COLUMN_GAP) == [950, 450]
    got = exercise_badges.assign(badges, anchors, 1000)
    assert got["links"][1]["exercises"] == [1, 2, 3, 4, 7]
    assert got["links"][2]["exercises"] == [5]


def test_lone_numbers_are_columns_when_no_column_has_two():
    anchors = [{"n": 1, "box": [930, 200, 950, 224]}, {"n": 2, "box": [430, 200, 450, 224]}]
    assert exercise_badges._columns(anchors, 1000, exercise_badges.COLUMN_GAP) == [950, 450]


@pytest.mark.parametrize(
    "starts, span, want",
    [([3, 4], (3, 8), 5), ([3, 8], (3, 8), None), ([], (3, 8), 3)],
)
def test_after_examples_starts_after_the_last_example_page(starts, span, want):
    assert (
        exercise_badges.after_examples([{"n": i + 1, "start": s} for i, s in enumerate(starts)], span) == want
    )


def test_stage_without_an_exercises_marker_scans_after_the_last_example(tmp_path, monkeypatch):
    book = _book(tmp_path, monkeypatch)
    monkeypatch.setattr(exercise_badges, "exercises_start", lambda *args: None)  # كتاب بلا markers.exercises
    assert main([str(tmp_path), "exercise_badges"]) == 0
    assert _lessons(book, "exercise_badges")["1.1"]["value"] == [
        {"example": 1, "exercises": [1, 2], "pages": [5]},
        {"example": 2, "exercises": [3], "pages": [5]},
    ]
