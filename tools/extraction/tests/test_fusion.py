"""دمج OCR والرؤية والجدول: نصوص وقوائم مختلقة بصفحات قليلة، لا بيانات دليل حقيقية."""

import json

from tools.extraction import fusion
from tools.extraction.__main__ import main

from .conftest import TOY_PAGES, make_book


def setup(tmp_path, ocr, vision=None, tables=None, **over):
    book = make_book(tmp_path, ocr, dirs={"vision": "vision", "tables": "tables"}, **over)
    for name, data in (("vision", vision or {}), ("tables", tables or {})):
        (tmp_path / name).mkdir(exist_ok=True)
        for n, payload in data.items():
            (tmp_path / name / f"{n:04d}.json").write_text(json.dumps(payload), encoding="utf-8")
    return book


def test_status_both_ocr_vision_and_review_of_last_exercise(tmp_path):
    book = setup(
        tmp_path,
        {1: "1. أ\n2. ب", 2: "4. د"},
        {1: {"exercises": [1, 2, 3]}, 2: {"exercises": [4, 5]}},
    )
    r = fusion.fuse(book, 1, 2)
    assert r["exercises"] == {1: "both", 2: "both", 3: "vision", 4: "both", 5: "vision"}
    assert r["review_pages"] == {2}  # الرقم الأخير بلا جدول: تُعلَّم صفحته


def test_gap_is_filled_and_page_flagged(tmp_path):
    book = setup(tmp_path, {1: "1. أ\n3. ج"})
    r = fusion.fuse(book, 1, 1)
    assert r["exercises"][2] == "filled"
    assert r["review_pages"] == {1}


def test_stray_number_above_chain_is_rejected(tmp_path):
    book = setup(tmp_path, {1: "1. أ\n2. ب\n40. ز"})
    r = fusion.fuse(book, 1, 1)
    assert sorted(r["exercises"]) == [1, 2]
    assert r["rejected"]["exercises"] == {1: [40]}


def test_table_caps_exercises_and_replaces_last_exercise_flag(tmp_path):
    book = setup(
        tmp_path,
        {1: "1. أ\n2. ب\n10. ي"},
        tables={1: {"rows": [{"exercises": [1, 2, 3]}]}},
    )
    r = fusion.fuse(book, 1, 1)
    assert sorted(r["exercises"]) == [1, 2, 3]  # 3 من الجدول وحده، و10 فوق آخر تمرين فيه
    assert r["rejected"]["exercises"] == {1: [10]}
    assert r["exercises"][3] == "ocr"  # الجدول يُعامَل مصدر OCR


def test_degenerate_vision_list_is_dropped_to_ocr_agreement(tmp_path):
    book = setup(tmp_path, {1: "1. أ\n2. ب\n3. ج"}, {1: {"exercises": list(range(1, 26))}})
    r = fusion.fuse(book, 1, 1)
    assert set(r["exercises"]) == {1, 2, 3}
    assert 25 in r["rejected"]["exercises"][1]


def test_vision_only_example_above_ocr_needs_two_pages(tmp_path):
    ocr = {1: "مثال 1", 2: "شرح"}
    (tmp_path / "a").mkdir()
    one = fusion.fuse(setup(tmp_path / "a", ocr, {1: {"examples": [1, 2]}}), 1, 2)
    assert set(one["examples"]) == {1}
    assert one["rejected"]["examples"] == {1: [2]}
    (tmp_path / "b").mkdir()
    two = fusion.fuse(setup(tmp_path / "b", ocr, {1: {"examples": [1, 2]}, 2: {"examples": [2]}}), 1, 2)
    assert set(two["examples"]) == {1, 2}


def test_practices_from_marker_and_name(tmp_path):
    book = setup(
        tmp_path,
        {1: "ممارسات الرياضيات\nنمذج\nجملة شرح طويلة جدا لا تبدأ باسم"},
        practices={"marker": "ممارسات الرياضيات", "names": {"MP.4": ["نمذج"]}},
    )
    # رمز MP.n الحرفي لا يُلتقط من النص: norm يصغّر اللاتيني فلا يطابق النمط (سلوك الأصل محفوظ)؛ الاسم هو الطريق
    assert fusion.fuse(book, 1, 1)["practices"] == {"MP.4": "ocr"}


def test_build_json_shape_and_summary(tmp_path):
    book = setup(tmp_path, {1: "1. أ", 2: "2. ب"})
    layout = {"lessons": [{"id": "1.1", "pages_pdf": [1, 2]}, {"id": "1.2", "pages_pdf": None}]}
    res = fusion.build(book, layout)
    assert list(res["lessons"]) == ["1.1"]
    assert res["lessons"]["1.1"]["exercises"] == {"1": "ocr", "2": "ocr"}
    s = fusion.summarize(res)
    assert s["lessons"] == 1 and s["by_status"]["ocr"] == 2


def test_stage_writes_output_and_skips_when_unchanged(tmp_path, capsys):
    book = setup(tmp_path, TOY_PAGES, layout={"id_pattern": r"(?<![\d.a-z])(\d{1,2})\.(\d{1,2})(?![\d.])"})
    assert main([str(book.root), "fusion"]) == 0
    out = json.loads((book.out / "fusion.json").read_text(encoding="utf-8"))
    assert set(out["lessons"]) == {"1.1", "1.2"}
    capsys.readouterr()
    assert main([str(book.root), "fusion"]) == 0
    assert "تُخطيت" in capsys.readouterr().out
