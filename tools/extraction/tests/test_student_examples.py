"""مرحلتا student_ocr وstudent_examples: المسح بصناديق OCR مختلقة (بلا ملف)، ثم المرحلتان كلتاهما على PDF صغير مولَّد
(pymupdf وnumpy وPillow؛ بيئة guide_extract) بقارئ ونموذج رؤية مزيَّفين؛ لا صفحة كتاب حقيقية."""

import json
import re
from contextlib import contextmanager
from pathlib import Path

import pytest

from tools.extraction import llama, ocr, printed_pages, student_examples, student_ocr
from tools.extraction.__main__ import main, run_stage

from .conftest import TOY_PAGES, make_book

ID_PATTERN = r"(?<![\d.a-z])(\d{1,2})\.(\d{1,2})(?![\d.])"
TRY = "حاول أن تحل التمرين"
W, H = 2550, 3263  # صفحة 612×783 نقطة بدقة 300
K = 72 / 300  # نقاط لكل بكسل من الصناديق
TOP, BOTTOM = 0.04 * H, 0.95 * H
LAYOUT = {"lessons": [{"id": "1.1", "pages_pdf": [3, 5]}]}
GUIDE = {3: 10, 4: 11, 5: 12}  # صفحة الدليل → المطبوع
STUDENT = {12: 10, 13: 11, 14: 12}  # صفحة ملف الطالب → المطبوع


def _label(y, x1=2300):
    return ("مثال", [x1 - 200, y, x1, y + 60])


def _try(y, n=None, x1=2300):
    return (f"{TRY} {n}" if n else TRY, [x1 - 700, y, x1, y + 60])


def _line(y, x0=300, x1=2300):
    return ("سطر", [x0, y, x1, y + 50])


def _book(root, examples=2, **over):
    course = root / "courses" / "toy" / "lessons"
    course.mkdir(parents=True, exist_ok=True)
    (course / "lesson_1_1.json").write_text(
        json.dumps({"lesson": "1.1", "examples": [{"number": n + 1} for n in range(examples)]}),
        encoding="utf-8",
    )
    return make_book(
        root,
        TOY_PAGES,
        dirs={"student_render": "srender", "student_ocr": "socr", "examples_student": "clips"},
        layout={"id_pattern": ID_PATTERN},
        student_pdf={"dir": ".", "pattern": "student.pdf"},
        student_examples={"course": "toy", "courses_dir": "courses", "vision": False, **over},
    )


def _scan(book, pages):
    """مسح الدرس 1.1 بصفحات مختلقة (صفحة ملف → صناديقها)، بلا صور: أرقام «حاول أن تحل» من نص الصندوق."""
    got = student_examples.scan(
        book, LAYOUT, GUIDE, STUDENT, lambda p: pages.get(p), lambda p: (W, H), lambda p: None, None
    )
    return got["lessons"]["1.1"], got["try"]["lessons"]["1.1"]


def _spans(lesson):
    return [
        [(lesson["columns"][s["column"]].page, s["y0"], s["y1"]) for s in item["segments"]]
        for item in lesson["examples"]
    ]


# ───── المسح (نقي) ─────
def test_a_label_line_opens_an_example_and_its_try_line_closes_it(tmp_path):
    book = _book(tmp_path)
    lesson, tried = _scan(
        book, {12: [_try(2000, 7), _label(300), _line(400), _try(900, 4), _label(1200), _line(1300)]}
    )
    assert (lesson["status"], lesson["found"], lesson["expected"]) == ("ok", 2, 2)
    assert [item["end"] for item in lesson["examples"]] == ["try", "try"]
    assert _spans(lesson) == [[(12, 300.0, 900.0)], [(12, 1200.0, 2000.0)]]
    assert (tried["status"], tried["source"]) == ("review", "derived")
    assert tried["value"] == [
        {"example": 1, "exercises": [4], "pages": [10]},  # الصفحة المطبوعة لسطره
        {"example": 2, "exercises": [7], "pages": [10]},
    ]


def test_an_example_without_a_try_line_ends_at_the_next_label_or_the_exercises_marker(tmp_path):
    book = _book(tmp_path, examples=3)
    pages = {
        12: [_label(300), _label(1200), _try(2000, 7), _label(2400)],
        13: [_line(300), ("تمارين", [2000, 500, 2300, 560]), _label(900)],  # ما بعد العلامة لا يُقرأ
    }
    lesson, tried = _scan(book, pages)
    assert (lesson["status"], lesson["found"]) == ("ok", 3)
    assert [item["end"] for item in lesson["examples"]] == ["label", "try", "stop"]
    assert _spans(lesson) == [
        [(12, 300.0, 1200.0)],
        [(12, 1200.0, 2000.0)],
        [(12, 2400.0, BOTTOM), (13, TOP, 500.0)],
    ]
    assert [row["exercises"] for row in tried["value"]] == [[], [7]]  # المثال الأخير بلا سطر يسقط من الروابط


def test_an_unread_try_line_still_ends_the_example_and_the_lesson_end_closes_the_last(tmp_path):
    book = _book(tmp_path)
    lesson, tried = _scan(book, {12: [_label(300), _try(900), _label(1200)]})
    assert [item["end"] for item in lesson["examples"]] == ["try_unread", "lesson"]
    assert _spans(lesson)[0] == [(12, 300.0, 900.0)]
    assert _spans(lesson)[1] == [(12, 1200.0, BOTTOM), (13, TOP, BOTTOM), (14, TOP, BOTTOM)]
    assert (tried["status"], tried["unread"]) == ("missing", 1)


def test_an_example_crossing_the_page_continues_in_the_next(tmp_path):
    book = _book(tmp_path, examples=1)
    lesson, tried = _scan(book, {12: [_label(2800)], 13: [_line(300), _try(600, 4)]})
    assert lesson["status"] == "ok"
    assert _spans(lesson) == [[(12, 2800.0, BOTTOM), (13, TOP, 600.0)]]
    assert tried["value"] == [{"example": 1, "exercises": [4], "pages": [11]}]


def _two_columns():
    right = [_line(y, 1400, 2400) for y in range(400, 2900, 100)]
    left = [_line(y, 150, 1150) for y in range(400, 2900, 100)]
    events = [_label(300, 1150), _try(1500, 5, 1150), _label(300, 2400), _try(1500, 3, 2400)]
    return [*left, *right, *events]


def test_two_columns_are_read_from_the_right(tmp_path):
    book = _book(tmp_path)
    lesson, tried = _scan(book, {12: _two_columns()})
    assert lesson["status"] == "ok"
    first, second = (lesson["columns"][item["segments"][0]["column"]] for item in lesson["examples"])
    assert (first.index, second.index) == (0, 1) and first.x0 == second.x1 and 1150 < first.x0 < 1400
    assert (first.x1, second.x0) == (W, 0)
    assert [row["exercises"] for row in tried["value"]] == [[3], [5]]


def test_columns_need_events_on_both_sides_and_can_be_forced(tmp_path):
    # عمودا خطوات وشرحها في مثال واحد: فاصل في الوسط وأسطر في الجهتين، وسطر «مثال» في جهة واحدة
    steps = [box for box in _two_columns() if box[0] == "سطر"]
    page = [*steps, _label(300, 2400), _try(2950, 3, 2400)]
    found = student_examples.page_events(page, TRY, [])
    cfg = student_examples.DEFAULTS
    assert student_examples.page_columns(page, found, (W, H), cfg) == [(0.0, float(W))]
    assert len(student_examples.page_columns(page, found, (W, H), cfg, forced=2)) == 2
    both = student_examples.page_events(_two_columns(), TRY, [])
    assert student_examples.page_columns(_two_columns(), both, (W, H), cfg, forced=1) == [(0.0, float(W))]
    book = _book(tmp_path, column_pages={12: 1})
    lesson, _ = _scan(book, {12: _two_columns()})
    assert len(lesson["columns"]) == 3  # عمود لكل صفحة من الثلاث


def test_a_count_that_differs_from_the_course_is_review(tmp_path):
    book = _book(tmp_path, examples=4)
    lesson, _ = _scan(book, {12: [_label(300), _try(900, 4), _label(1200), _try(2000, 7)]})
    assert (lesson["status"], lesson["reasons"], lesson["found"], lesson["expected"]) == (
        "review",
        ["count"],
        2,
        4,
    )


def test_trailing_labels_beyond_the_expected_count_are_dropped(tmp_path):
    book = _book(tmp_path)
    pages = {12: [_label(300), _try(900, 4), _label(1200), _try(2000, 7)], 13: [_label(400), _label(900)]}
    lesson, _ = _scan(book, pages)
    assert (lesson["status"], lesson["found"], lesson["dropped"]) == ("ok", 2, 2)


def test_an_example_opened_by_a_try_line_has_no_start_and_a_lesson_without_pages_is_review(tmp_path):
    book = _book(tmp_path)
    lesson, _ = _scan(book, {12: [_label(300), _try(900, 4), _try(2000, 7)]})  # فات سطر «مثال» الثاني
    assert (lesson["status"], lesson["reasons"], lesson["opened"]) == ("review", ["unlabeled"], 1)
    got = student_examples.scan(
        book, LAYOUT, GUIDE, {12: 10, 14: 13}, lambda p: [], lambda p: (W, H), lambda p: None, None
    )
    assert got["lessons"]["1.1"]["reasons"] == ["pages"]
    assert got["lessons"]["1.1"]["missing_pages"] == [11, 12]


def test_lesson_pages_fill_gaps_between_consecutive_neighbours():
    pages, printed, missing = student_examples.lesson_pages([3, 6], {3: 10, 6: 13}, {10: 12, 13: 15})
    assert pages == [(12, 10), (13, 11), (14, 12), (15, 13)]
    assert (printed, missing) == ([10, 13], [])
    assert student_examples.lesson_pages(None, {}, {}) == (None, None, [])


# ───── جدول الصفحات المطبوعة ─────
def _numbered(place, wrong=None):
    """صفحات فيها رقمها المطبوع (الصفحة + 8) في الترويسة أو التذييل، ورقم ثابت في الجهة الأخرى."""
    y = {"footer": 3150, "header": 60}
    other = "header" if place == "footer" else "footer"
    return {
        page: [
            (str(page + 8), [1200, y[place], 1300, y[place] + 50]),
            ("7", [1200, y[other], 1300, y[other] + 50]),
            _line(1000),
        ]
        for page in range(1, 9)
        if page != wrong
    }


@pytest.mark.parametrize("place", ["footer", "header"])
def test_page_table_takes_the_band_that_gives_a_strictly_increasing_table(place):
    got = student_ocr.page_table(_numbered(place), student_examples.DEFAULTS, (W, H))
    assert got["band"] == place
    assert got["table"] == {page: page + 8 for page in range(1, 9)}


def test_page_table_uses_the_shared_logic_and_rejects_a_non_monotone_table():
    read = _numbered("footer", wrong=4)
    filled = student_ocr.page_table(read, student_examples.DEFAULTS, (W, H))
    assert (filled["table"][4], filled["filled"]) == (12, 1)  # سدّ `printed_pages.fill` نفسه
    read[4] = [("3", [1200, 3150, 1300, 3200])]
    with pytest.raises(printed_pages.PrintedPagesError):
        student_ocr.page_table(read, student_examples.DEFAULTS, (W, H))
    fixed = student_ocr.page_table(read, {**student_examples.DEFAULTS, "skip": [4]}, (W, H))
    assert fixed["table"][4] == 12
    banded = student_ocr.page_table(
        _numbered("header"), {**student_examples.DEFAULTS, "band": [0.0, 0.0, 1.0, 0.1]}, (W, H)
    )
    assert banded["band"] == "config"


# ───── الرؤية والمقارنة والأسماء ─────
def test_verdict_judges_each_clip_by_its_place_in_the_example():
    fine = {"number": 2, "title": True, "cut_bottom": False, "cut_side": False}
    assert student_examples.verdict(fine, 2, first=True, last=True) == (fine, [])
    assert student_examples.verdict({**fine, "number": 0}, 2, True, True)[1] == []  # لم يُقرأ الرقم
    assert student_examples.verdict({**fine, "number": 3}, 2, True, True)[1] == ["number"]
    assert student_examples.verdict({**fine, "title": False}, 2, True, True)[1] == ["title"]
    cut = {"number": 0, "title": False, "cut_bottom": True, "cut_side": True}
    assert student_examples.verdict(cut, 2, first=False, last=False)[1] == ["cut_side"]  # تتمة يتلوها جزء آخر
    assert student_examples.verdict(cut, 2, first=False, last=True)[1] == ["cut_bottom", "cut_side"]
    assert student_examples.verdict({}, 2, True, True) == (None, ["no_answer"])
    assert student_examples.verdict({**fine, "number": "نص"}, 2, True, True) == (None, ["no_answer"])


def test_a_missed_title_is_settled_by_the_read_number_at_the_ocr_label_or_by_the_top_strip():
    missed = {"number": 2, "title": False, "cut_bottom": False, "cut_side": False}
    verdict = student_examples.verdict
    # الرقم المقروء المطابق وسطر «مثال» عند أعلى المقطع دليل كافٍ؛ وأحدهما وحده لا يكفي
    assert verdict(missed, 2, True, True, anchored=True) == (missed, [])
    assert verdict(missed, 2, True, True, anchored=False)[1] == ["title"]
    assert verdict({**missed, "number": 0}, 2, True, True, anchored=True)[1] == ["title"]
    assert verdict({**missed, "number": 3}, 2, True, True, anchored=True)[1] == ["title", "number"]
    # جواب الشريط العلوي: عنوانه يثبت العنوان، ورقمه المقروء يتقدّم على رقم الصورة كلها
    assert verdict({**missed, "number": 0}, 2, True, True, top={"number": 0, "title": True})[1] == []
    assert verdict({**missed, "number": 3}, 2, True, True, top={"number": 2, "title": True})[1] == []
    assert verdict({**missed, "number": 0}, 2, True, True, True, {"number": 2, "title": False})[1] == []
    assert verdict(missed, 2, True, True, top={"number": 5, "title": True})[1] == ["number"]
    assert verdict(missed, 2, True, True, top={"number": 0, "title": False})[1] == ["title"]
    assert verdict(missed, 2, True, True, top=None)[1] == ["title"]
    cut = {**missed, "cut_bottom": True, "cut_side": True}  # القطع لا يغيّره دليل العنوان
    assert verdict(cut, 2, True, True, anchored=True)[1] == ["cut_bottom", "cut_side"]
    assert student_examples.top_reading({"number": "4", "title": 1}) == {"number": 4, "title": True}
    assert student_examples.top_reading({"title": True}) is None
    assert student_examples.anchored(1.2, 12.0, 2.0) and student_examples.anchored(-2.0, 12.0, 2.0)
    assert not student_examples.anchored(None, 12.0, 2.0)  # المقطع لا يبدأ بجزء سطر «مثال»
    assert not student_examples.anchored(30.0, 12.0, 2.0) and not student_examples.anchored(-9.0, 12.0, 2.0)


def test_compare_counts_agreement_per_lesson():
    def result(rows):
        return {"lessons": {"2.6": {"value": [{"example": n, "exercises": e} for n, e in rows]}}}

    student = result([(1, [3]), (2, [9]), (3, [12]), (5, [20])])
    guide = result([(1, []), (2, [9]), (3, [14]), (4, [17])])
    assert student_examples.compare(student, guide) == {
        "2.6": {
            "agree": 1,
            "differ": [{"example": 3, "student": [12], "guide": [14]}],
            "student_only": [{"example": 1, "exercises": [3]}, {"example": 5, "exercises": [20]}],
            "guide_only": [{"example": 4, "exercises": [17]}],
        }
    }
    assert student_examples.compare(student, None) is None


def test_clip_names_are_the_names_publish_assets_accepts():
    source = Path(__file__).resolve().parents[3] / "apps" / "assets" / "services.py"
    assert f'CLIP = re.compile(r"{student_examples.NAME.pattern}")' in source.read_text(encoding="utf-8")
    assert student_examples.NAME.match(student_examples.clip_name("2.6", 1, 87, False))
    assert student_examples.NAME.match(student_examples.clip_name("2.10", 12, 104, True))["cont"]
    assert student_examples.NAME.match(student_examples.clip_name("2.6", 1, 1087, False)) is None


def test_rise_above_finds_the_top_of_the_ink_block():
    inked = [False, False, True, True, True, False, True]
    assert student_examples.rise_above(inked, 4, 5) == 2
    assert student_examples.rise_above(inked, 5, 5) == 6  # الصف نفسه أبيض
    assert student_examples.rise_above(inked, 4, 1) is None  # لا صف أبيض ضمن الحد
    assert student_examples.rise_above([True, True], 1, 5) == 0


def test_settings_are_validated():
    assert student_examples.errors({}) == []
    bad = {"student_examples": {"ocr_dpi": 0, "columns": 3, "band": [0, 1], "vision": "no", "approved": "x"}}
    assert len(student_examples.errors(bad)) == 5
    assert student_examples.errors({"student_examples": {"end_patterns": ["("]}})
    strip = {"student_examples": {"title_dpi": 12, "title_strip": 0, "title_top": "x"}}
    assert len(student_examples.errors(strip)) == 3


# ───── المرحلتان على PDF مولَّد ─────
PAGE_ONE = [
    _label(400),
    _line(520),
    _line(600),
    _try(1200, 4),
    _label(2600),
    _line(2720),
    ("10", [1200, 3150, 1300, 3200]),
]
PAGE_TWO = [
    _line(300),
    _line(450),
    _try(700, 7),
    _label(1000),
    _line(1120),
    ("تمارين", [2000, 2000, 2300, 2060]),
    _label(2400),
    ("11", [1200, 3150, 1300, 3200]),
]
PAGE_THREE = [("12", [1200, 3150, 1300, 3200])]
PAGES = {1: PAGE_ONE, 2: PAGE_TWO, 3: PAGE_THREE}
CLIPS = {"1.1_m1_p10.png", "1.1_m2_p10.png", "1.1_m2_p11_cont.png", "1.1_m3_p11.png"}


def _stage_book(tmp_path, monkeypatch, examples=3, **over):
    """كتاب طالب من ثلاث صفحات: المثال 1 يغلقه سطر «حاول أن تحل»، والمثال 2 يعبر إلى الصفحة التالية، والمثال 3 بلا سطر
    تغلقه علامة التمارين. كل صندوق مختلق مرسوم حبرًا في موضعه."""
    pymupdf = pytest.importorskip("pymupdf")
    pytest.importorskip("numpy")
    pytest.importorskip("PIL.Image")
    book = _book(tmp_path, examples=examples, **over)
    if not (tmp_path / "student.pdf").exists():
        doc = pymupdf.open()
        for number in sorted(PAGES):
            page = doc.new_page(width=612, height=783)
            for _, box in PAGES[number]:
                page.draw_rect(pymupdf.Rect(*(v * K for v in box)), color=None, fill=(0.1, 0.1, 0.1))
        doc.save(tmp_path / "student.pdf")
        doc.close()
    monkeypatch.setattr(
        ocr, "read_page", lambda image: tuple(map(list, zip(*PAGES[int(Path(image).stem)], strict=True)))
    )
    monkeypatch.setattr(ocr, "read_scored", lambda crop: ("", 0.0))  # الرقم من نص الصندوق
    (tmp_path / "layout.json").write_text(json.dumps(LAYOUT), encoding="utf-8")
    (tmp_path / "printed_pages.json").write_text(json.dumps({"3": 10, "4": 11, "5": 12}), encoding="utf-8")
    guide = {"1.1": {"value": [{"example": n, "exercises": [e]} for n, e in ((1, 4), (2, 9), (3, 12))]}}
    (tmp_path / "exercise_try.json").write_text(json.dumps({"lessons": guide}), encoding="utf-8")
    return book


def _report(book):
    return json.loads(book.output("student_examples").read_text(encoding="utf-8"))


def test_student_ocr_renders_reads_and_writes_the_page_table(tmp_path, monkeypatch, capsys):
    book = _stage_book(tmp_path, monkeypatch)
    assert main([str(tmp_path), "student_ocr"]) == 0
    out = capsys.readouterr().out
    assert '"rendered": 3' in out and '"read": 3' in out and '"band": "footer"' in out and '"table": 3' in out
    assert json.loads(book.output("student_pages").read_text(encoding="utf-8")) == {"1": 10, "2": 11, "3": 12}
    assert student_examples.png_size(tmp_path / "srender" / "0001.png") == (W, H)
    assert sorted(p.name for p in (tmp_path / "socr").iterdir()) == ["0001.json", "0002.json", "0003.json"]
    assert run_stage(book, "student_ocr") is False  # مختومة
    monkeypatch.setattr(ocr, "read_page", None)  # المقروء لا يُعاد ولو أُعيدت المرحلة
    assert main([str(tmp_path), "student_ocr", "--force"]) == 0
    assert '"rendered": 0' in capsys.readouterr().out


def test_student_examples_cuts_clips_from_the_pdf_and_reports_numbers(tmp_path, monkeypatch, capsys):
    book = _stage_book(tmp_path, monkeypatch)
    assert main([str(tmp_path), "student_ocr"]) == 0
    capsys.readouterr()
    assert main([str(tmp_path), "student_examples"]) == 0
    out = capsys.readouterr().out
    for part in ('"lessons": 1', '"expected": 3', '"found": 3', '"written": 4', '"review": 0', '"agree": 1'):
        assert part in out
    assert '"lessons": {"1.1": [1, 1, 0, 1]}' in out  # متفقة، مختلفة، للطالب وحده، للدليل وحده
    assert {p.name for p in (tmp_path / "clips").iterdir()} == CLIPS
    assert not (tmp_path / "clips_review").exists()
    report = _report(book)
    clips = {clip["file"]: clip for clip in report["clips"]}
    assert set(clips) == CLIPS and all(clip["status"] == "ok" for clip in clips.values())
    assert (report["lessons"]["1.1"]["status"], report["lessons"]["1.1"]["found"]) == ("ok", 3)
    first = clips["1.1_m1_p10.png"]
    # من أعلى حبر سطر «مثال» إلى أسفل آخر سطر قبل «حاول أن تحل»، بعرض الحبر وهامشه
    assert first["box"] == pytest.approx([300 * K - 2, 400 * K, 2300 * K + 2, 650 * K + 2], abs=1)
    assert (first["student_page"], first["printed_page"], first["dpi"], first["kind"], first["end"]) == (
        1,
        10,
        600,
        "vector",
        "try",
    )
    assert first["width"] == pytest.approx((first["box"][2] - first["box"][0]) * 600 / 72, abs=2)
    assert student_examples.png_size(tmp_path / "clips" / first["file"]) == (first["width"], first["height"])
    head, tail = clips["1.1_m2_p10.png"], clips["1.1_m2_p11_cont.png"]
    assert head["box"][3] == pytest.approx(2770 * K + 2, abs=1)  # رقم الصفحة في التذييل خارج المقطع
    assert tail["box"][1::2] == pytest.approx([300 * K - 2, 500 * K + 2], abs=1)
    assert tail["cont"] and tail["last"] and not head["last"]
    last = clips["1.1_m3_p11.png"]
    assert (last["end"], last["box"][3]) == ("stop", pytest.approx(1170 * K + 2, abs=1))
    tried = json.loads(book.output("student_try").read_text(encoding="utf-8"))["lessons"]["1.1"]
    assert tried["status"] == "review"
    assert tried["value"] == [
        {"example": 1, "exercises": [4], "pages": [10]},
        {"example": 2, "exercises": [7], "pages": [11]},
    ]
    assert report["try"]["1.1"]["differ"] == [{"example": 2, "student": [7], "guide": [9]}]
    for name in ("student_examples", "student_try"):  # أرقام وحدها، بلا نص
        assert not re.search("[ء-ي]", book.output(name).read_text(encoding="utf-8"))
    assert run_stage(book, "student_examples") is False  # مختومة


def test_a_lesson_whose_count_differs_writes_no_clip_and_exits_7(tmp_path, monkeypatch, capsys):
    book = _stage_book(tmp_path, monkeypatch, examples=5)
    assert main([str(tmp_path), "student_ocr"]) == 0
    assert main([str(tmp_path), "student_examples"]) == 7
    assert '"review_lessons": {"1.1": ["count"]}' in capsys.readouterr().out
    assert not list((tmp_path / "clips").iterdir())
    report = _report(book)
    assert report["clips"] == [] and report["lessons"]["1.1"]["status"] == "review"
    assert len(report["lessons"]["1.1"]["examples"]) == 3  # مواضعها في التقرير للتشخيص
    assert run_stage(book, "student_ocr") is False
    assert main([str(tmp_path), "student_examples"]) == 7  # لم تُختم


def _fake_vision(monkeypatch, rejected):
    asked = []

    @contextmanager
    def serve(book, size="small", ctx=None):
        yield object()

    def asker(server):
        def ask(image, question, fmt):
            assert Path(image).exists() and fmt == student_examples.CHECK
            asked.append(Path(image).name)
            match = student_examples.NAME.match(Path(image).name)
            return {
                "number": int(match["n"]),
                "title": not match["cont"],
                "cut_bottom": Path(image).name in rejected,
                "cut_side": False,
            }

        return ask

    monkeypatch.setattr(llama, "serve", serve)
    monkeypatch.setattr(llama, "asker", asker)
    return asked


def test_a_clip_the_vision_model_rejects_is_not_written_until_approved(tmp_path, monkeypatch, capsys):
    bad = "1.1_m2_p11_cont.png"
    asked = _fake_vision(monkeypatch, {bad})
    book = _stage_book(tmp_path, monkeypatch, vision=True)
    assert main([str(tmp_path), "student_ocr"]) == 0
    assert main([str(tmp_path), "student_examples"]) == 7
    assert sorted(asked) == sorted(CLIPS)
    assert {p.name for p in (tmp_path / "clips").iterdir()} == {"1.1_m1_p10.png", "1.1_m3_p11.png"}
    # المثال الذي خالف مقطع منه لا يُكتب منه شيء، ويبقى للمراجعة خارج مجلد النشر
    assert {p.name for p in (tmp_path / "clips_review").iterdir()} == {bad, "1.1_m2_p10.png"}
    clips = {clip["file"]: clip for clip in _report(book)["clips"]}
    assert (clips[bad]["status"], clips[bad]["problems"]) == ("review", ["cut_bottom"])
    assert clips[bad]["vision"] == {"number": 2, "title": False, "cut_bottom": True, "cut_side": False}
    assert (clips["1.1_m2_p10.png"]["status"], clips["1.1_m2_p10.png"]["problems"]) == ("review", ["sibling"])
    assert clips["1.1_m1_p10.png"]["status"] == "ok"
    capsys.readouterr()
    book = _stage_book(tmp_path, monkeypatch, vision=True, approved=[bad])
    assert main([str(tmp_path), "student_examples"]) == 0
    out = capsys.readouterr().out
    assert '"written": 4' in out and '"approved": 1' in out
    assert {p.name for p in (tmp_path / "clips").iterdir()} == CLIPS
    assert not (tmp_path / "clips_review").exists()
    assert {clip["status"] for clip in _report(book)["clips"]} == {"ok", "approved"}


def _titleless_vision(monkeypatch, numbers, strips):
    """نموذج لا يرى العنوان في صورة المقطع كلها: `numbers` ما يقرؤه رقمًا فيها لكل مقطع (الافتراضي رقم المثال)،
    و`strips` جوابه عن شريط كل مقطع. يعيد ما سُئل عنه: (اسم الصورة، مقاسها، هل السؤال سؤال الشريط)."""
    asked = []

    @contextmanager
    def serve(book, size="small", ctx=None):
        yield object()

    def asker(server):
        def ask(image, question, fmt):
            name = Path(image).name
            strip = name.startswith(student_examples.TOP)
            assert fmt == (student_examples.TITLE if strip else student_examples.CHECK)
            assert question == (student_examples.TITLE_QUESTION if strip else student_examples.QUESTION)
            asked.append((name, student_examples.png_size(Path(image)), strip))
            if strip:
                return strips[name.removeprefix(student_examples.TOP)]
            number = numbers.get(name, int(student_examples.NAME.match(name)["n"]))
            return {"number": number, "title": False, "cut_bottom": False, "cut_side": False}

        return ask

    monkeypatch.setattr(llama, "serve", serve)
    monkeypatch.setattr(llama, "asker", asker)
    return asked


def test_a_title_the_model_misses_is_settled_without_approval(tmp_path, monkeypatch, capsys):
    unread, wrong = "1.1_m1_p10.png", "1.1_m3_p11.png"
    strips = {unread: {"number": 1, "title": True}, wrong: {"number": 3, "title": False}}
    asked = _titleless_vision(monkeypatch, {unread: 0, wrong: 8}, strips)
    book = _stage_book(tmp_path, monkeypatch, vision=True)
    assert main([str(tmp_path), "student_ocr"]) == 0
    assert main([str(tmp_path), "student_examples"]) == 0
    assert '"written": 4' in capsys.readouterr().out
    assert {p.name for p in (tmp_path / "clips").iterdir()} == CLIPS
    assert not (tmp_path / "clips_review").exists()  # ولا صور الرؤية وأشرطتها
    clips = {clip["file"]: clip for clip in _report(book)["clips"]}
    assert all(clip["status"] == "ok" and clip["problems"] == [] for clip in clips.values())
    # سطر «مثال» من صناديق OCR عند أعلى كل مقطع أول، والتتمة بلا سطر
    assert [clips[name]["label_top"] for name in sorted(CLIPS)] == [
        pytest.approx(0, abs=1),
        pytest.approx(0, abs=1),
        None,
        pytest.approx(0, abs=1),
    ]
    # الرقم المقروء المطابق مع السطر يكفي بلا سؤال ثانٍ؛ والشريط يُسأل عنه لما لم يُقرأ رقمه أو خالف وحده
    assert sorted(name for name, _, strip in asked if strip) == sorted(
        f"top_{name}" for name in (unread, wrong)
    )
    assert sorted(name for name, _, strip in asked if not strip) == sorted(CLIPS)
    assert clips["1.1_m2_p10.png"]["top"] is None and clips["1.1_m2_p11_cont.png"]["top"] is None
    assert clips[unread]["top"] == strips[unread] and clips[wrong]["top"] == strips[wrong]
    assert clips[unread]["vision"]["title"] is False  # جواب الصورة كلها يبقى في التقرير كما هو
    # الشريط أعلى المقطع بعرضه كله وبدقة `title_dpi`، لا صورته المصغّرة
    sizes = {name: size for name, size, _ in asked}
    box = clips[unread]["box"]
    assert sizes[f"top_{unread}"] == pytest.approx(((box[2] - box[0]) * 300 / 72, 60 * 300 / 72), abs=2)
    assert sizes[unread][0] == pytest.approx((box[2] - box[0]) * 200 / 72, abs=2)


def test_a_title_neither_the_number_nor_the_strip_settles_stays_for_review(tmp_path, monkeypatch, capsys):
    bad = "1.1_m2_p10.png"
    strips = {bad: {"number": 0, "title": False}, "1.1_m3_p11.png": {}}
    _titleless_vision(monkeypatch, {bad: 0, "1.1_m3_p11.png": 0}, strips)
    book = _stage_book(tmp_path, monkeypatch, vision=True)
    assert main([str(tmp_path), "student_ocr"]) == 0
    assert main([str(tmp_path), "student_examples"]) == 7
    assert {p.name for p in (tmp_path / "clips").iterdir()} == {"1.1_m1_p10.png"}
    assert {p.name for p in (tmp_path / "clips_review").iterdir()} == CLIPS - {"1.1_m1_p10.png"}
    clips = {clip["file"]: clip for clip in _report(book)["clips"]}
    assert (clips[bad]["status"], clips[bad]["problems"]) == ("review", ["title"])
    assert clips["1.1_m2_p11_cont.png"]["problems"] == ["sibling"]
    assert clips["1.1_m3_p11.png"]["problems"] == ["title"] and clips["1.1_m3_p11.png"]["top"] is None
    assert not re.search("[ء-ي]", book.output("student_examples").read_text(encoding="utf-8"))


def test_a_vision_server_that_does_not_start_exits_4(tmp_path, monkeypatch):
    @contextmanager
    def serve(book, size="small", ctx=None):
        raise RuntimeError("no engine")
        yield

    monkeypatch.setattr(llama, "serve", serve)
    _stage_book(tmp_path, monkeypatch, vision=True)
    assert main([str(tmp_path), "student_ocr"]) == 0
    assert main([str(tmp_path), "student_examples"]) == 4
    assert not list((tmp_path / "clips").iterdir())
