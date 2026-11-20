"""مرحلتا printed_pages وexercise_links على الكتاب الاصطناعي: صناديق وأرقام رؤية مختلقة، لا نص دليل."""

import json

import pytest
import yaml

from tools.extraction import exercise_links, printed_pages, stamps
from tools.extraction.__main__ import main, run_stage
from tools.extraction.config import Book

from .conftest import TOY_PAGES, make_book

ID_PATTERN = r"(?<![\d.a-z])(\d{1,2})\.(\d{1,2})(?![\d.])"
PAGE = (1000, 2000)
FOOT = [480, 1900, 520, 1940]  # داخل شريط التذييل الافتراضي
BODY = [480, 600, 520, 640]


def _boxes(book, numbers, extra=None):
    """صناديق كل صفحة: نص في المتن يثبّت مقاسها، ورقمها (أو أرقامها) في التذييل."""
    folder = book.out / "boxes"
    folder.mkdir(exist_ok=True)
    for page in range(1, book["pages"] + 1):
        boxes = [["كلمة", [0, 0, *PAGE]], ["7", BODY]]  # رقم في المتن ليس رقم صفحة
        found = numbers.get(page, [])
        boxes += [[str(n), FOOT] for n in (found if isinstance(found, list) else [found])]
        boxes += (extra or {}).get(page, [])
        (folder / f"{page:04d}.json").write_text(json.dumps(boxes, ensure_ascii=False), encoding="utf-8")


def _table(book):
    return json.loads((book.out / "printed_pages.json").read_text(encoding="utf-8"))


# ───── printed_pages ─────
def test_candidates_are_footer_digit_boxes_only():
    boxes = [("12", FOOT), ("٣٤", FOOT), ("12", BODY), ("ص 5", FOOT), ("1234", FOOT), ("0", FOOT)]
    assert printed_pages.candidates(boxes, PAGE, printed_pages.DEFAULTS["band"]) == {12, 34}


def test_raw_paddle_output_in_the_ocr_folder_is_read(toy):
    raw = {"res": {"rec_texts": [" 41 "], "rec_boxes": [FOOT]}}
    (toy.dir("ocr") / "0003.json").write_text(json.dumps(raw), encoding="utf-8")
    assert printed_pages.stored_boxes(toy, 3) == [("41", FOOT)]
    assert printed_pages.stored_boxes(toy, 4) is None


def test_stage_writes_the_table_fills_gaps_and_stamps(toy, capsys):
    # الصفحة 4 بلا رقم بين جارتين بإزاحة واحدة فتُسدّ، و9 و10 بلا جارة لاحقة فتبقيان مجهولتين
    _boxes(toy, {2: 12, 3: 13, 5: 15, 6: 16, 7: 17, 8: 18})
    assert main([str(toy.root), "printed_pages"]) == 0
    assert _table(toy) == {"2": 12, "3": 13, "4": 14, "5": 15, "6": 16, "7": 17, "8": 18}
    assert '"filled": 1' in capsys.readouterr().out
    assert run_stage(toy, "printed_pages") is False  # مختومة: لم يتغير مدخلها
    (toy.out / "boxes" / "0009.json").write_text(json.dumps([["19", FOOT]]), encoding="utf-8")
    assert run_stage(toy, "printed_pages") is True
    assert _table(toy)["9"] == 19


def test_two_footer_numbers_are_settled_by_the_usual_offset(toy):
    _boxes(toy, {2: 12, 3: 13, 4: [14, 3], 5: [40, 41]})
    result = printed_pages.build(toy, lambda p: printed_pages.stored_boxes(toy, p))
    assert result["table"] == {2: 12, 3: 13, 4: 14}
    assert result["ambiguous"] == [5]


def test_non_monotone_table_is_rejected_and_nothing_is_written(toy, capsys):
    _boxes(toy, {2: 12, 3: 13, 4: 11, 5: 15})
    assert main([str(toy.root), "printed_pages"]) == 6
    err = capsys.readouterr().err
    assert "غير رتيب" in err and "[3, 4]" in err
    assert not (toy.out / "printed_pages.json").exists()
    assert not (toy.out / stamps.FILE).exists()  # لم تُختم
    assert main([str(toy.root), "printed_pages"]) == 6  # فتُعاد وتُرفض ثانيةً


def test_repeated_number_is_not_monotone():
    with pytest.raises(printed_pages.PrintedPagesError, match="غير رتيب"):
        printed_pages.validate({2: 12, 3: 12})
    printed_pages.validate({2: 12, 3: 13, 9: 40})


@pytest.mark.parametrize("number", [0, 1000, -3])
def test_number_outside_range_is_rejected(number):
    with pytest.raises(printed_pages.PrintedPagesError, match="خارج 1-999"):
        printed_pages.validate({2: number})


def test_skip_and_set_let_the_owner_fix_a_misread(tmp_path):
    cfg = {"skip": [4], "set": {5: 15}}
    book = make_book(tmp_path, TOY_PAGES, printed_pages=cfg)
    _boxes(book, {2: 12, 3: 13, 4: 11, 6: 16})
    assert main([str(tmp_path), "printed_pages"]) == 0
    assert _table(book) == {"2": 12, "3": 13, "4": 14, "5": 15, "6": 16}


# ───── exercise_links ─────
CFG = {"max_exercise": 60, "jump": {"exercises": 5}, "degenerate": 20}


def test_link_follows_numbers_sharing_a_page():
    pages = {
        3: ({1}, {1, 2}),  # صفحة المثال 1 وفيها تدريباه
        4: ({2}, set()),
        5: ({1, 2}, {3, 4}),  # صفحة تمارين تحيل إلى المثالين
        6: (set(), {5, 6}),  # بلا إحالة
        7: ({9}, {7}),  # رقم مثال غير مقبول
    }
    got = exercise_links.link((2, 7), {1, 2}, pages, CFG)
    assert got["links"] == [
        {"example": 1, "exercises": [1, 2, 3, 4], "pages": [3, 5]},
        {"example": 2, "exercises": [3, 4], "pages": [5]},
    ]
    assert got["unlinked"] == [5, 6, 7] and got["shared_pages"] == [5]


def test_link_drops_stray_and_degenerate_exercise_lists():
    pages = {3: ({1}, {1, 2, 40}), 4: ({1}, set(range(1, 31)))}
    got = exercise_links.link((3, 4), {1}, pages, CFG)
    assert got["links"] == [{"example": 1, "exercises": [1, 2], "pages": [3]}]


def _vision_book(tmp_path):
    book = make_book(tmp_path, TOY_PAGES, dirs={"vision": "hybrid"}, layout={"id_pattern": ID_PATTERN})
    (tmp_path / "hybrid").mkdir()
    seen = {
        3: {"examples": [1], "exercises": []},
        4: {"examples": [2], "exercises": [1]},
        5: {"examples": [1], "exercises": [2, 3]},
        7: {"examples": [1], "exercises": []},
        8: {"examples": [], "exercises": [1, 2]},
    }
    for page, data in seen.items():
        (tmp_path / "hybrid" / f"{page:04d}.json").write_text(json.dumps(data), encoding="utf-8")
    return book


def test_stage_builds_examples_then_writes_review_links(tmp_path):
    book = _vision_book(tmp_path)
    assert main([str(tmp_path), "exercise_links"]) == 0
    assert (book.out / "examples.json").exists()
    lessons = json.loads((book.out / "exercise_links.json").read_text(encoding="utf-8"))["lessons"]
    first = lessons["1.1"]
    assert (first["source"], first["status"]) == ("derived", "review")
    assert first["value"] == [
        {"example": 1, "exercises": [2, 3], "pages": [5]},
        {"example": 2, "exercises": [1], "pages": [4]},
    ]
    assert lessons["1.2"]["status"] == "missing" and lessons["1.2"]["unlinked"] == [1, 2]
    assert run_stage(book, "exercise_links") is False


def test_owner_correction_approves_a_lesson(tmp_path):
    book = _vision_book(tmp_path)
    approved = [{"example": 1, "exercises": [2, 3]}, {"example": 2, "exercises": [1]}]
    (book.out / "corrections.yaml").write_text(
        yaml.safe_dump(
            [
                {
                    "stage": "exercise_links",
                    "path": ["lessons", "1.1"],
                    "value": approved,
                    "reason": "راجعه المالك على الكتاب",
                }
            ],
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    assert main([str(tmp_path), "exercise_links"]) == 0
    entry = json.loads((book.out / "exercise_links.json").read_text(encoding="utf-8"))["lessons"]["1.1"]
    assert (entry["value"], entry["source"], entry["status"]) == (approved, "teacher", "ok")


def test_lessons_without_vision_are_missing(toy):
    Book.load(toy.root)
    assert main([str(toy.root), "exercise_links"]) == 0
    lessons = json.loads((toy.out / "exercise_links.json").read_text(encoding="utf-8"))["lessons"]
    assert {v["status"] for v in lessons.values()} == {"missing"}


# ───── practice: تمارين قسم «تمارين» بجانب صفوف «حاول أن تحل» ─────
def _read_stage(book, name, value, **extra):
    """مخرج مرحلة ربط مقروء للدرس 1.1 مكتوبًا باليد (المرحلتان تحتاجان صورًا وتعرّفًا)."""
    lessons = {"1.1": {"value": value, "source": "derived", "status": "review", "unlinked": [], **extra}}
    (book.out / f"{name}.json").write_text(
        json.dumps({"book": book.id, "lessons": lessons}), encoding="utf-8"
    )


def _links(book):
    return json.loads((book.out / "exercise_links.json").read_text(encoding="utf-8"))["lessons"]


def test_try_lesson_with_badges_gets_the_badge_rows_as_practice(tmp_path):
    book = _vision_book(tmp_path)
    tried = [
        {"example": 1, "exercises": [2], "pages": [3]},
        {"example": 2, "exercises": [], "pages": []},  # بلا سطر مقروء: يُقترح له practice كغيره
    ]
    _read_stage(book, "exercise_try", tried)
    badges = [
        {"example": 1, "exercises": [1, 2, 3], "pages": [5]},
        {"example": 2, "exercises": [2, 4], "pages": [5]},
    ]
    _read_stage(book, "exercise_badges", badges, badges=2, unreadable=0)
    assert main([str(tmp_path), "exercise_links"]) == 0
    first, second = _links(book)["1.1"], _links(book)["1.2"]
    assert (first["method"], first["status"], first["value"]) == ("try", "review", tried)
    practice = first["practice"]
    assert (practice["source"], practice["status"], practice["method"]) == ("derived", "review", "badges")
    # كما قُرئت: 2 تمرين «حاول أن تحل» الخام يبقى هنا، والكاتب يحذف ما في صفوف try النهائية
    assert practice["value"] == badges
    assert "practice" not in second  # درس بلا «حاول أن تحل»: صفوفه وحدها
    summary = exercise_links.summarize({"lessons": _links(book)})
    assert summary["practice_review"] == ["1.1"] and "1.1" in summary["review"]


def test_exercise_the_owner_removes_from_try_rows_stays_in_practice(tmp_path):
    book = _vision_book(tmp_path)
    _read_stage(book, "exercise_try", [{"example": 1, "exercises": [2], "pages": [3]}])
    badges = [{"example": 1, "exercises": [1, 2, 3], "pages": [5]}]
    _read_stage(book, "exercise_badges", badges, badges=1, unreadable=0)
    corrected = [{"example": 1, "exercises": [1]}]  # المالك: تمرين المثال 1 لا 2
    (book.out / "corrections.yaml").write_text(
        yaml.safe_dump(
            [
                {
                    "stage": "exercise_links",
                    "path": ["lessons", "1.1"],
                    "value": corrected,
                    "reason": "راجعه المالك على الكتاب",
                }
            ],
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    assert main([str(tmp_path), "exercise_links"]) == 0
    entry = _links(book)["1.1"]
    assert (entry["value"], entry["status"]) == (corrected, "ok")
    assert entry["practice"]["value"] == badges  # 2 لم يعد في صفوف try، فيبقى من تمارين المثال
    summary = exercise_links.summarize({"lessons": _links(book)})
    assert summary["practice_review"] == ["1.1"] and "1.1" not in summary["review"]


def test_practice_needs_a_readable_badge_and_a_try_lesson(tmp_path):
    book = _vision_book(tmp_path)
    rows = [{"example": 1, "exercises": [1, 2], "pages": [5]}]
    _read_stage(book, "exercise_badges", rows, badges=1, unreadable=0)
    assert main([str(tmp_path), "exercise_links"]) == 0
    first = _links(book)["1.1"]
    assert first["method"] == "badges" and "practice" not in first  # الشارات صفوف الدرس نفسها
    _read_stage(book, "exercise_try", [{"example": 1, "exercises": [2], "pages": [3]}])
    _read_stage(book, "exercise_badges", rows, badges=1, unreadable=1)
    assert main([str(tmp_path), "exercise_links", "--force"]) == 0
    first = _links(book)["1.1"]
    assert first["method"] == "try" and "practice" not in first  # لا شارة مقروءة


def test_owner_corrections_approve_try_rows_and_practice_separately(tmp_path):
    book = _vision_book(tmp_path)
    _read_stage(book, "exercise_try", [{"example": 1, "exercises": [2], "pages": [3]}])
    _read_stage(
        book,
        "exercise_badges",
        [{"example": 1, "exercises": [1, 2, 3], "pages": [5]}],
        badges=1,
        unreadable=0,
    )
    approved = [{"example": 1, "exercises": [2]}]

    def correct(*items):
        (book.out / "corrections.yaml").write_text(
            yaml.safe_dump(
                [{"stage": "exercise_links", "reason": "راجعه المالك على الكتاب", **item} for item in items],
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        assert main([str(tmp_path), "exercise_links", "--force"]) == 0
        return _links(book)["1.1"]

    entry = correct({"path": ["lessons", "1.1"], "value": approved})
    assert (entry["value"], entry["status"]) == (approved, "ok")  # التصحيح يغلب، وpractice تنتظر اعتمادها
    assert entry["practice"]["status"] == "review"
    assert entry["practice"]["value"] == [{"example": 1, "exercises": [1, 2, 3], "pages": [5]}]
    wanted = [{"example": 1, "exercises": [3]}]
    entry = correct(
        {"path": ["lessons", "1.1"], "value": approved},
        {"path": ["lessons", "1.1", "practice"], "value": wanted},
    )
    assert (entry["practice"]["value"], entry["practice"]["source"], entry["practice"]["status"]) == (
        wanted,
        "teacher",
        "ok",
    )
    assert (entry["value"], entry["status"]) == (approved, "ok")
