import json

import yaml

from tools.extraction.__main__ import main


def test_validate_ok_and_errors(toy, capsys):
    assert main([str(toy.root), "validate"]) == 0
    assert "toy" in capsys.readouterr().out
    (toy.root / "book.yaml").write_text(yaml.safe_dump({"id": "x"}), encoding="utf-8")
    assert main([str(toy.root), "validate"]) == 2
    assert "معيب" in capsys.readouterr().err


def test_missing_book_exits_two(tmp_path, capsys):
    assert main([str(tmp_path), "layout"]) == 2
    assert "book.yaml" in capsys.readouterr().err


def test_layout_examples_checks_stages_write_outputs(toy, capsys):
    for stage in ("layout", "examples", "checks"):
        assert main([str(toy.root), stage]) == 0
    out = capsys.readouterr().out
    assert '"lessons": 2' in out
    layout = json.loads((toy.out / "layout.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in layout["lessons"]] == ["1.1", "1.2"]
    ex = json.loads((toy.out / "examples.json").read_text(encoding="utf-8"))
    assert ex["lessons"]["1.1"]["source"] == "derived"
    assert (toy.out / "checks.json").exists()


def test_later_stage_builds_layout_when_absent(toy):
    assert not (toy.out / "layout.json").exists()
    assert main([str(toy.root), "examples"]) == 0
    assert (toy.out / "layout.json").exists()
