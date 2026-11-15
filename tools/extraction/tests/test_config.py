import copy

import pytest
import yaml

from tools.extraction.config import Book, validate

from .conftest import base_cfg, make_book


def test_valid_config_has_no_errors():
    assert validate(base_cfg()) == []


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda c: c.pop("markers"), "markers"),
        (lambda c: c["layout"].update(anchor="x"), "layout.anchor"),
        (lambda c: c["layout"].update(end="x"), "layout.end"),
        (lambda c: c["layout"].update(anchor="analysis"), "markers.analysis"),
        (lambda c: c["layout"].update(end="quiz"), "markers.quiz"),
        (lambda c: c["layout"].update(image_min=[0, 5]), "image_min"),
        (lambda c: c["standards"].update(pattern="("), "standards.pattern"),
        (lambda c: c["markers"].update(objective_end=[]), "objective_end"),
        (lambda c: c.update(pages=0), "pages"),
        (lambda c: c.setdefault("examples", {}).update(pattern="["), "examples.pattern"),
    ],
)
def test_invalid_config_reports(mutate, needle):
    cfg = copy.deepcopy(base_cfg())
    mutate(cfg)
    assert any(needle in e for e in validate(cfg))


def test_load_rejects_bad_and_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        Book.load(tmp_path)
    (tmp_path / "book.yaml").write_text(yaml.safe_dump({"id": "x"}), encoding="utf-8")
    with pytest.raises(ValueError, match="معيب"):
        Book.load(tmp_path)


def test_paths_and_pdf_choice(tmp_path):
    book = make_book(tmp_path, {1: "نص"})
    assert book.dir("ocr") == book.out / "ocr"
    assert book.output("layout").name == "layout.json"
    assert book.page_text(1) == "نص"
    with pytest.raises(FileNotFoundError):
        book.pdf()
    (tmp_path / "a.pdf").write_bytes(b"1")
    (tmp_path / "b(1).pdf").write_bytes(b"22")
    cfg = base_cfg()
    cfg["pdf"]["prefer_suffix"] = "(1).pdf"
    (tmp_path / "book.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    assert Book.load(tmp_path).pdf().name == "b(1).pdf"


def test_generic_output_name_takes_precedence(tmp_path):
    book = make_book(tmp_path, {1: "x"}, outputs={"objectives": "old.json", "generic_objectives": "new.json"})
    assert book.output("objectives").name == "new.json"
    assert book.output("layout").name == "layout.json"
