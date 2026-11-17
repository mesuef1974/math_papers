"""تمثيلات الأمثلة بالرؤية: جواب مختلق مكان الخادم، ومقاطع وصور اصطناعية لا من دليل حقيقي."""

import json

import pytest
import yaml

from tools.extraction import reps
from tools.extraction.config import Book

from .conftest import TOY_PAGES, make_book

Q = reps.QUESTIONS


def put(root, folder, page, data):
    path = root / folder
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{page:04d}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def read(root, folder, page):
    return json.loads((root / folder / f"{page:04d}.json").read_text(encoding="utf-8"))


def toy(tmp_path, **cfg):
    book = make_book(
        tmp_path,
        TOY_PAGES,
        dirs={
            "crops": "crops",
            "gold": "gold",
            "v1": "v1",
            "v2": "v2",
            "v3": "v3",
            "v5": "v5",
            "render": "render",
        },
        reps=cfg,
    )
    layout = {"lessons": [{"id": "1.1", "pages_pdf": [3, 5]}, {"id": "3.1", "pages_pdf": [7, 8]}]}
    (tmp_path / "layout.json").write_text(json.dumps(layout), encoding="utf-8")
    return book


def thumbs(root, *pairs):
    (root / "crops").mkdir(exist_ok=True)
    for page, k in pairs:
        (root / "crops" / f"{page:04d}_{k}_thumb.png").write_bytes(b"x")


def answering(table):
    """جواب مختلق: table[نص السؤال] = قائمة أجوبة متتابعة (تتكرر الأخيرة)."""
    seen: dict[str, int] = {}

    def ask(image, text, fmt):
        seq = table.get(text, [False])
        i = seen.get(text, 0)
        seen[text] = i + 1
        ok = seq[min(i, len(seq) - 1)]
        return {"yes": ok} if "yes" in str(fmt) else {"continues": ok, "n": 2 if ok else 0}

    return ask


def test_replace_inserts_name_first_and_keeps_previous_list(tmp_path):
    book = toy(tmp_path)
    put(
        tmp_path, "v1", 3, [{"n": 1, "representations": ["جدول", "بياني"]}, {"n": 2, "representations": None}]
    )
    thumbs(tmp_path, (3, 0), (3, 1))
    spec = {"kind": "replace", "src": "v1", "dst": "v2", "previous": "representations_v1",
            "questions": {"بياني": ["graphic"]}}  # fmt: skip
    got = reps.run_pass(book, answering({Q["graphic"]: [True]}), spec)
    out = read(tmp_path, "v2", 3)
    assert out[0]["representations"] == ["بياني", "جدول"]
    assert out[0]["representations_v1"] == ["جدول", "بياني"]
    assert out[1]["representations"] is None and "representations_v1" not in out[1]
    assert got == {"pages": 1, "items": 1, "added": 0}


def test_replace_drops_name_when_answer_is_no(tmp_path):
    book = toy(tmp_path)
    put(tmp_path, "v1", 3, [{"n": 1, "representations": ["بياني", "جدول"]}])
    thumbs(tmp_path, (3, 0))
    spec = {"kind": "replace", "src": "v1", "dst": "v2", "questions": {"بياني": ["graphic"]}}
    reps.run_pass(book, answering({}), spec)
    assert read(tmp_path, "v2", 3)[0]["representations"] == ["جدول"]


def test_add_needs_majority_of_three_and_any_question(tmp_path):
    book = toy(tmp_path)
    put(tmp_path, "v1", 3, [{"n": 1, "representations": ["جدول"]}, {"n": 2, "representations": []}])
    thumbs(tmp_path, (3, 0), (3, 1))
    spec = {"kind": "add", "src": "v1", "dst": "v2", "questions": {"جبري": ["algebra", "solve"]}}
    # المثال 1: السؤال الأول نعم مرة واحدة من ثلاث (يسقط) والثاني نعم مرتين من ثلاث (يمر)؛ المثال 2: لا دائمًا
    ask = answering(
        {Q["algebra"]: [True, False, False, False, False, False], Q["solve"]: [True, True, False]}
    )
    got = reps.run_pass(book, ask, spec)
    out = read(tmp_path, "v2", 3)
    assert out[0]["representations"] == ["جدول", "جبري"]
    assert out[1]["representations"] == []
    assert out[0]["representations_v2"] == ["جدول"]
    assert got["added"] == 1


def test_add_skips_name_already_present_without_asking(tmp_path):
    book = toy(tmp_path)
    put(tmp_path, "v1", 3, [{"n": 1, "representations": ["جبري"]}])
    thumbs(tmp_path, (3, 0))

    def boom(*a):
        raise AssertionError("لا يُسأل عن تمثيل موجود")

    reps.run_pass(book, boom, {"kind": "add", "src": "v1", "dst": "v2", "questions": {"جبري": ["algebra"]}})


def test_lessons_filter_and_resume(tmp_path):
    book = toy(tmp_path)
    put(tmp_path, "v1", 3, [{"n": 1, "representations": []}])
    put(tmp_path, "v1", 7, [{"n": 1, "representations": []}])
    thumbs(tmp_path, (3, 0), (7, 0))
    spec = {"kind": "add", "src": "v1", "dst": "v2", "lessons": ["3."], "questions": {"جدول": ["table"]}}
    ask = answering({Q["table"]: [True]})
    assert reps.run_pass(book, ask, spec)["pages"] == 1
    assert not (tmp_path / "v2" / "0003.json").exists() and read(tmp_path, "v2", 7)
    (tmp_path / "v2" / "0007.json").write_text("[]", encoding="utf-8")
    assert reps.run_pass(book, ask, spec)["pages"] == 0  # المنجَز لا يُعاد
    assert read(tmp_path, "v2", 7) == []


class Crop:
    def save(self, path):
        path.write_bytes(b"c")


def continuation_cfg(**over):
    cont = {
        "dst": "v5",
        "groups": [
            {"lessons": ["1."], "sources": ["v2"], "questions": {"جدول": ["table"], "بياني": ["axes"]}}
        ],
    }
    return {"continuation": {**cont, **over}}


def test_continuation_adds_to_owner_example_and_records_pages(tmp_path):
    book = toy(tmp_path, **continuation_cfg())
    put(tmp_path, "v2", 3, [{"n": 1, "representations": ["جبري"]}])
    put(tmp_path, "v2", 4, [{"n": 2, "representations": []}])
    # الصفحة 4 تتمة للمثال 1 (أقرب مثال سابق)، والصفحة 5 بعد آخر مثال تتبع المثال 2 إن قرأ النموذج «تابع المثال 2»
    regions = {4: Crop(), 5: Crop()}
    ask = answering({Q["continue"]: [True], Q["table"]: [True], Q["axes"]: [False]})
    got = reps.run_continuation(book, ask, regions.get)
    assert got == {"lessons": 1, "continuations": 2, "added": 2}
    one, two = read(tmp_path, "v5", 3)[0], read(tmp_path, "v5", 4)[0]
    assert one["representations"] == ["جبري", "جدول"] and one["continuation_pages"] == [4]
    assert one["representations_v4"] == ["جبري"]
    assert two["representations"] == ["جدول"] and two["continuation_pages"] == [5]
    assert (tmp_path / "crops" / "cont_0004.png").exists()


def test_continuation_after_last_example_must_name_that_example(tmp_path):
    book = toy(tmp_path, **continuation_cfg())
    put(tmp_path, "v2", 3, [{"n": 1, "representations": []}])
    ask = answering({Q["continue"]: [False], Q["table"]: [True]})  # صفحة تمارين لا تتمة
    got = reps.run_continuation(book, ask, {4: Crop()}.get)
    assert got["continuations"] == 0
    assert read(tmp_path, "v5", 3)[0]["representations"] == []


def test_continuation_picks_group_by_lesson_prefix_and_ignores_others(tmp_path):
    cfg = continuation_cfg()
    cfg["continuation"]["groups"].append(
        {"lessons": ["3."], "sources": ["v3", "v2"], "questions": {"جدول": ["table"]}}
    )
    book = toy(tmp_path, **cfg)
    put(tmp_path, "v2", 7, [{"n": 1, "representations": []}])  # درس 3.1: يُقرأ v3 ثم v2 (يسقط إلى v2)
    put(tmp_path, "v3", 8, [{"n": 2, "representations": []}])
    got = reps.run_continuation(book, answering({Q["table"]: [True]}), {8: Crop()}.get)
    assert got["lessons"] == 1 and read(tmp_path, "v5", 7)[0]["continuation_pages"] == [8]
    assert reps.run_continuation(book, answering({}), lambda p: None)["continuations"] == 0


def test_errors_flag_unknown_dirs_questions_and_kinds(tmp_path):
    bad = {
        "passes": [
            {"kind": "zip", "src": "v1", "dst": "v2", "questions": {"أ": ["table"]}},
            {"kind": "add", "src": "nope", "dst": "v2", "questions": {"أ": ["ghost"]}},
            {"kind": "replace", "src": "v1", "dst": "v2", "questions": {"أ": ["table"], "ب": ["table"]}},
        ],
        "continuation": {"dst": "nope", "groups": [{"sources": ["v1", "x"], "questions": {}}]},
    }
    cfg = {"dirs": {"v1": "a", "v2": "b"}, "reps": bad}
    text = "؛ ".join(reps.errors(cfg))
    for needle in ("kind", "nope", "ghost", "replace يلزمه", "x", "questions"):
        assert needle in text
    assert reps.errors({"dirs": {}}) == []
    book = toy(tmp_path)
    cfg = yaml.safe_load((tmp_path / "book.yaml").read_text(encoding="utf-8"))
    cfg["reps"] = bad
    (tmp_path / "book.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="reps"):
        Book.load(book.root)


def test_book_question_overrides_default(tmp_path):
    book = toy(tmp_path, questions={"table": "سؤال مخصص"})
    assert reps.question(book, "table") == "سؤال مخصص"
    assert reps.question(book, "axes") == Q["axes"]


def test_evaluate_scores_versions_against_gold(tmp_path):
    book = toy(tmp_path)
    gold = {"lesson": "1.1", "examples": [
        {"page_pdf": 3, "n": 1, "representation": "جدول + بياني"},
        {"page_pdf": 3, "n": 2, "representation": "جبري"},
    ]}  # fmt: skip
    (tmp_path / "gold").mkdir()
    (tmp_path / "gold" / "lesson_1_1.json").write_text(json.dumps(gold, ensure_ascii=False), encoding="utf-8")
    put(
        tmp_path,
        "v1",
        3,
        [{"n": 1, "representations": ["جدول"]}, {"n": 2, "representations": ["جبري", "سياق حياتي"]}],
    )
    put(
        tmp_path,
        "v2",
        3,
        [{"n": 1, "representations": ["جدول", "بياني"]}, {"n": 2, "representations": ["جبري"]}],
    )
    rows = {r["version"]: r for r in reps.evaluate(book, ["v1", "v2", "v3"])}
    assert "v3" not in rows  # مجلد غائب
    assert rows["v1"]["fn"] == 1 and rows["v1"]["fp"] == 1 and rows["v1"]["exact"] == 0
    assert rows["v2"]["exact"] == 2 and rows["v2"]["precision"] == 1.0 and rows["v2"]["recall"] == 1.0
    assert rows["v2"]["per_lesson"] == {"1.1": "2/2"}


def test_region_finds_space_above_first_badge_and_rejects_empty(tmp_path):
    np = pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image")
    book = toy(tmp_path)
    cfg = reps.CONTINUATION_DEFAULTS

    def page(n, ink=True, badge_y=1000):
        arr = np.full((2000, 1000, 3), 255, dtype=np.uint8)
        if ink:
            arr[400:600, 100:400] = 0
        if badge_y:
            arr[badge_y : badge_y + 30, 300:380] = cfg["badge"]
        (tmp_path / "render").mkdir(exist_ok=True)
        Image.fromarray(arr).save(tmp_path / "render" / f"{n:04d}.png")

    page(4)
    crop = reps.region(book, 4, cfg)
    assert crop.size == (
        440,
        1000 - 15 - 250,
    )  # من 0.06 إلى 0.50 من العرض، ومن 0.125 من الارتفاع إلى ما قبل الشارة بـ15
    page(5, ink=False)
    assert reps.region(book, 5, cfg) is None  # لا حبر فيها
    page(6, badge_y=300)
    assert reps.region(book, 6, cfg) is None  # أقل من min_gap
    assert reps.region(book, 7, cfg) is None  # لا صفحة مصيَّرة
