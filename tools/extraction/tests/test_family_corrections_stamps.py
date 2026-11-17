"""وراثة الإعداد وتصحيحات الكتاب اليدوية وأختام المراحل، على الكتاب الاصطناعي."""

import copy
import json

import pytest
import yaml

from tools.extraction import corrections, objectives, stamps
from tools.extraction.__main__ import main, run_stage
from tools.extraction.config import Book, deep_merge, resolve

from .conftest import TOY_PAGES, base_cfg, make_book

ID_PATTERN = r"(?<![\d.a-z])(\d{1,2})\.(\d{1,2})(?![\d.])"


def _write(path, data):
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


# ───── extends ─────
def test_deep_merge_merges_maps_and_replaces_lists_without_mutation():
    base = {"a": {"x": 1, "y": [1, 2]}, "b": 1}
    over = {"a": {"y": [9]}, "c": 2}
    snapshot = copy.deepcopy(base)
    assert deep_merge(base, over) == {"a": {"x": 1, "y": [9]}, "b": 1, "c": 2}
    assert base == snapshot


def test_book_extends_a_family_file_by_relative_path(tmp_path):
    family = base_cfg()
    family.pop("id")
    family.pop("title")
    _write(tmp_path / "family.yaml", family)
    _write(tmp_path / "book.yaml", {"extends": "family.yaml", "id": "kid", "title": "ابن", "pages": 3})
    book = Book.load(tmp_path)
    assert book.id == "kid" and book["language"] == "ar" and book["pages"] == 3
    assert "extends" not in book.cfg


def test_extends_resolves_a_named_family_shipped_with_the_tool(tmp_path):
    _write(
        tmp_path / "book.yaml",
        {
            "extends": "ar_teacher_guide",
            "id": "fam",
            "title": "عائلة",
            "pages": 5,
            "out": ".",
            "pdf": {"dir": ".", "pattern": "*.pdf"},
            "markers": base_cfg()["markers"],
            "standards": {"pattern": r"X\.\d"},
            "layout": {"anchor": "opener", "end": "next_opener", "image_min": [10, 10]},
        },
    )
    book = Book.load(tmp_path)
    assert book.dir("ocr").name == "guide_paddle"
    assert book["layout"]["unit_gap"] == 8 and book["layout"]["anchor"] == "opener"  # دمج لا استبدال


def test_extends_cycle_and_missing_parent_are_errors(tmp_path):
    _write(tmp_path / "a.yaml", {"extends": "b.yaml"})
    _write(tmp_path / "b.yaml", {"extends": "a.yaml"})
    with pytest.raises(ValueError, match="دورة"):
        resolve(tmp_path / "a.yaml")
    _write(tmp_path / "c.yaml", {"extends": "nope.yaml"})
    with pytest.raises(FileNotFoundError):
        resolve(tmp_path / "c.yaml")


# ───── المعجم ونمط الترقيم لكل كتاب ─────
def test_lexicon_follows_language_or_explicit_name(tmp_path):
    book = make_book(tmp_path, TOY_PAGES)
    assert book.lexicon_path.name == "bloom_lexicon_ar.json"
    assert objectives.lexicon(book)[0] == objectives.lexicon()[0]
    cfg = base_cfg(language="fr")
    _write(tmp_path / "book.yaml", cfg)
    with pytest.raises(ValueError, match="معجم"):
        Book.load(tmp_path)
    own = tmp_path / "lex.json"
    own.write_text(json.dumps({"version": "t", "entries": {"calculer": ["apply", 0.9]}}), encoding="utf-8")
    cfg["bloom_lexicon"] = str(own)
    _write(tmp_path / "book.yaml", cfg)
    assert objectives.lexicon(Book.load(tmp_path)) == ("t", {"calculer": ("apply", 0.9)})


def test_id_format_is_configurable_and_validated(tmp_path):
    make_book(tmp_path, TOY_PAGES, layout={"id_pattern": ID_PATTERN, "id_format": "U{unit}-L{lesson}"})
    assert main([str(tmp_path), "layout"]) == 0
    layout = json.loads((tmp_path / "layout.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in layout["lessons"]] == ["U1-L1", "U1-L2"]
    _write(tmp_path / "book.yaml", base_cfg(layout={"id_format": "{unit}"}))
    with pytest.raises(ValueError, match="id_format"):
        Book.load(tmp_path)


# ───── التصحيحات ─────
def _correct(book, *items):
    _write(book.out / "corrections.yaml", list(items))


def test_correction_replaces_value_records_reason_and_survives_rerun(toy):
    _correct(
        toy,
        {"stage": "layout", "path": ["lessons", 0, "unit"], "value": 7, "reason": "وحدة مطبوعة في الغلاف"},
    )
    for _ in range(2):  # إعادة التشغيل من الصفر تعيد التصحيح نفسه
        assert main([str(toy.root), "layout", "--force"]) == 0
        layout = json.loads((toy.out / "layout.json").read_text(encoding="utf-8"))
        assert layout["lessons"][0]["unit"] == 7
        assert layout["corrections"] == [
            {"path": ["lessons", 0, "unit"], "before": 1, "after": 7, "reason": "وحدة مطبوعة في الغلاف"}
        ]


def test_correction_on_a_field_envelope_becomes_teacher_ok(toy):
    main([str(toy.root), "examples"])
    before = json.loads((toy.out / "examples.json").read_text(encoding="utf-8"))
    _correct(
        toy,
        {
            "stage": "examples",
            "path": ["lessons", "1.1"],
            "value": [],
            "reason": "لا أمثلة مستقلة في هذا الدرس",
        },
    )
    assert main([str(toy.root), "examples", "--force"]) == 0
    fixed = json.loads((toy.out / "examples.json").read_text(encoding="utf-8"))["lessons"]["1.1"]
    assert (fixed["value"], fixed["source"], fixed["status"], fixed["corrected"]) == (
        [],
        "teacher",
        "ok",
        True,
    )
    assert before["lessons"]["1.1"]["source"] == "derived"


@pytest.mark.parametrize(
    "item",
    [
        {"stage": "layout", "path": ["lessons", 0, "unit"], "value": 1},  # بلا سبب
        {"stage": "layout", "path": ["lessons", 0, "unit"], "value": 1, "reason": "قصير"},
        {"stage": "nope", "path": ["x"], "value": 1, "reason": "سبب كافٍ للتصحيح"},
        {"stage": "layout", "path": [], "value": 1, "reason": "سبب كافٍ للتصحيح"},
        {"stage": "layout", "path": ["lessons", 0, "unit"], "reason": "سبب كافٍ للتصحيح"},
    ],
)
def test_malformed_correction_is_rejected(toy, item):
    _correct(toy, item)
    with pytest.raises(corrections.CorrectionError):
        corrections.load(toy)


def test_stale_or_unreachable_corrections_fail_loudly_with_exit_three(toy, capsys):
    _correct(
        toy,
        {"stage": "layout", "path": ["lessons", 9, "unit"], "value": 1, "reason": "درس لم يعد موجودًا"},
    )
    assert main([str(toy.root), "layout", "--force"]) == 3
    assert "تصحيح مرفوض" in capsys.readouterr().err
    _correct(
        toy,
        {
            "stage": "layout",
            "path": ["lessons", 0, "unit"],
            "value": 2,
            "expect": 5,
            "reason": "كان الدرس في الوحدة 5",
        },
    )
    assert main([str(toy.root), "layout", "--force"]) == 3
    assert "تصحيح قديم" in capsys.readouterr().err


def test_other_stage_corrections_do_not_touch_this_stage(toy):
    _correct(toy, {"stage": "checks", "path": ["lessons"], "value": {}, "reason": "تصحيح مرحلة أخرى تمامًا"})
    assert main([str(toy.root), "layout"]) == 0
    assert "corrections" not in json.loads((toy.out / "layout.json").read_text(encoding="utf-8"))


# ───── الأختام ─────
def test_stage_skips_until_its_input_changes(toy, capsys):
    assert run_stage(toy, "layout") is True
    assert run_stage(toy, "layout") is False
    assert "تُخطيت" in capsys.readouterr().out
    (toy.root / "ocr" / "0003.txt").write_text("مثال 1\nنص مختلف", encoding="utf-8")
    assert run_stage(toy, "layout") is True  # تغيّر نص صفحة
    assert run_stage(toy, "layout", force=True) is True  # --force يتجاوز الختم


def test_missing_output_or_changed_correction_or_config_reruns(toy):
    run_stage(toy, "layout")
    (toy.out / "layout.json").unlink()
    assert run_stage(toy, "layout") is True
    assert run_stage(toy, "layout") is False
    _correct(
        toy, {"stage": "layout", "path": ["lessons", 0, "unit"], "value": 3, "reason": "تصحيح جديد للاختبار"}
    )
    assert run_stage(toy, "layout") is True
    cfg = yaml.safe_load((toy.root / "book.yaml").read_text(encoding="utf-8"))
    cfg["layout"]["max_span"] = 9
    _write(toy.root / "book.yaml", cfg)
    assert run_stage(Book.load(toy.root), "layout") is True


def test_downstream_stage_reruns_when_upstream_output_changes(toy):
    run_stage(toy, "layout")
    run_stage(toy, "examples")
    assert run_stage(toy, "examples") is False
    _correct(
        toy, {"stage": "layout", "path": ["lessons", 0, "unit"], "value": 4, "reason": "وحدة مصحَّحة يدويًا"}
    )
    run_stage(toy, "layout")
    assert run_stage(toy, "examples") is True


def test_stamps_file_lives_in_the_book_folder(toy):
    run_stage(toy, "layout")
    stored = json.loads((toy.out / stamps.FILE).read_text(encoding="utf-8"))
    assert set(stored) == {"layout"} and len(stored["layout"]) == 64
