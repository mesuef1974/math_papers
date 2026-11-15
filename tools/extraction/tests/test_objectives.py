import pytest

from tools.extraction import layout, objectives

from .conftest import TOY_PAGES, make_book

LEX = objectives.lexicon()[1]


def box(text, x0, y0, x1, y1):
    return (text, [x0, y0, x1, y1])


def items():
    """عمود أيمن: المقدمة ثم هدفان (الثاني سطران) ثم المصطلحات؛ وعمود أيسر يجب ألا يدخل."""
    return [
        box("المحتوى الأيسر الطويل جدا", 10, 120, 400, 150),
        box("ما ستتعلمه", 520, 100, 800, 130),
        box("حساب النهايات", 520, 150, 800, 180),
        box("تفسير سلوك الداله", 520, 220, 800, 250),
        box("عند اقتراب المتغير", 520, 252, 800, 280),
        box("المصطلحات", 520, 340, 800, 370),
        box("نص بعد النهاية", 520, 400, 800, 430),
    ]


def test_lexicon_loads_and_classify():
    version, lex = objectives.lexicon()
    assert version and "حساب" in lex
    assert objectives.classify("حساب النهايات", lex) == ("حساب", "تطبيق", 1.0)
    assert objectives.classify("استكشاف الدوال", lex)[1:] == ("unclassified", None)
    assert objectives.classify("", lex) == ("", "unclassified", None)
    assert objectives.classify("التفسير الجيد", lex)[0] == "تفسير"  # «ال» تسقط


def test_segment_by_gap_is_review_method(toy):
    found, method = objectives.segment(items(), toy, LEX)
    assert method == "gap"
    assert [o["text"] for o in found] == ["حساب النهايات", "تفسير سلوك الداله عند اقتراب المتغير"]
    assert [o["lines"] for o in found] == [1, 2]


def test_segment_by_checkmarks_overrides_gap(toy):
    marks = lambda a, z: [165, 235]  # noqa: E731
    found, method = objectives.segment(items(), toy, LEX, marks)
    assert method == "check" and len(found) == 2
    one_mark = lambda a, z: [165]  # noqa: E731
    found, _ = objectives.segment(items(), toy, LEX, one_mark)
    assert len(found) == 1 and "عند اقتراب" in found[0]["text"]


def test_segment_without_intro_is_none(toy):
    assert objectives.segment([box("نص", 0, 0, 10, 10)], toy, LEX) == ([], "none")


def test_column_left_and_all(tmp_path):
    book = make_book(tmp_path, TOY_PAGES, objectives={"column": "left"})
    left_items = [
        box("ما ستتعلمه", 10, 100, 300, 130),
        box("رسم الدوال", 10, 150, 300, 180),
        box("المصطلحات", 10, 300, 300, 330),
        box("عمود يمين", 600, 150, 800, 180),
    ]
    found, _ = objectives.segment(left_items, book, LEX)
    assert [o["text"] for o in found] == ["رسم الدوال"]


def test_build_statuses_and_summary(toy):
    lay = layout.build(toy)
    boxes_of = lambda page: items()  # noqa: E731
    result = objectives.build(toy, lay, boxes_of)
    one = result["lessons"]["1.1"]
    assert one["source"] == "guide" and one["status"] == "review"  # gap فلا ok
    assert [i["bloom"] for i in one["value"]] == ["تطبيق", "فهم"]
    assert one["value"][0]["source"] == {"text": "guide", "bloom": "derived"}
    ok = objectives.build(toy, lay, boxes_of, lambda p, a, z: [165, 235])
    assert ok["lessons"]["1.1"]["status"] == "ok"
    s = objectives.summarize(ok)
    assert s["objectives"] == 4 and s["unclassified"] == 0 and s["missing_lessons"] == []


def test_build_missing_when_no_opener_or_no_objectives(toy):
    lay = layout.build(toy)
    lay["lessons"][1]["opener"] = None
    result = objectives.build(toy, lay, lambda p: [box("لا مقدمة", 0, 0, 10, 10)])
    assert result["lessons"]["1.1"]["status"] == "missing"
    assert result["lessons"]["1.2"]["status"] == "missing"
    assert objectives.summarize(result)["missing_lessons"] == ["1.1", "1.2"]


def test_unclassified_verbs_are_not_guessed(toy):
    lay = layout.build(toy)
    unknown = [
        box("ما ستتعلمه", 520, 100, 800, 130),
        box("استكشاف الدوال", 520, 150, 800, 180),
        box("المصطلحات", 520, 300, 800, 330),
    ]
    result = objectives.build(toy, lay, lambda p: unknown, lambda p, a, z: [165])
    item = result["lessons"]["1.1"]["value"][0]
    assert item["bloom"] == "unclassified" and item["confidence"] is None and item["status"] == "review"


def test_checkmarks_detects_colored_runs(tmp_path):
    np = pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image")
    arr = np.full((400, 100, 3), 255, dtype=np.uint8)
    arr[100:112, 85:93] = (0, 112, 160)  # علامة
    arr[200:212, 85:93] = (0, 112, 160)
    arr[300:312, 85:93] = (46, 173, 227)  # شريط تركيز: لون آخر لا يُعد علامة
    path = tmp_path / "p.png"
    Image.fromarray(arr).save(path)
    cfg = {"check": {"x": [0.85, 0.93], "rgb": [0, 112, 160], "tol": 40}}
    assert objectives.checkmarks(path, cfg, 0, 400) == [105, 205]
    assert objectives.checkmarks(path, cfg, 150, 400) == [205]
    assert objectives.checkmarks(path, {}, 0, 400) == []
