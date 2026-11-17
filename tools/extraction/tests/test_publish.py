"""مرحلتا load وpublish: تُختبران بمشغّل مختلق يسجّل أوامر manage.py، بلا Django ولا قاعدة ولا تخزين."""

import json

import pytest
import yaml

from tools.extraction import publish, stamps
from tools.extraction.__main__ import main, run_stage
from tools.extraction.config import Book

from .conftest import TOY_PAGES, make_book

LOAD = {"course": "g10-s1", "index": True}
PUBLISH = {"course": "g10-s1", "clips": "clips"}


def toy(tmp_path, **over):
    dirs = {"clips": "clips", "lessons": "lessons"}
    book = make_book(tmp_path, TOY_PAGES, dirs=dirs, **over)
    (tmp_path / "clips").mkdir()
    (tmp_path / "clips" / "1.1_m1_p3.png").write_bytes(b"png")
    (tmp_path / "lessons").mkdir()
    (tmp_path / "lessons" / "lesson_1_1.json").write_text("{}", encoding="utf-8")
    return book


class Recorder:
    """بديل run_manage: يسجّل الوسائط ويعيد سطرًا يشبه تقرير الأمر."""

    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def __call__(self, book, args):
        self.calls.append(args)
        if args[0] == self.fail_on:
            raise publish.PublishError(f"فشل {args[0]}: سبب")
        return f"{args[0]}: تم\nسطر ثانٍ"


@pytest.fixture
def recorder(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(publish, "run_manage", rec)
    return rec


def reload(tmp_path, **over):
    cfg = yaml.safe_load((tmp_path / "book.yaml").read_text(encoding="utf-8"))
    cfg.update(over)
    (tmp_path / "book.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return Book.load(tmp_path)


def test_config_errors():
    assert publish.errors({}) == []
    assert publish.errors({"load": LOAD, "publish": PUBLISH, "dirs": {"clips": "c"}}) == []
    errs = publish.errors(
        {"load": {"course": "G10"}, "publish": {"course": "g10-s1", "clips": "x"}, "dirs": {}}
    )
    assert any("load.course" in e for e in errs) and any("publish.clips" in e for e in errs)
    assert publish.errors({"load": 3, "dirs": {}}) == ["load يجب أن يكون خريطة"]
    assert any("load.index" in e for e in publish.errors({"load": {"course": "a", "index": "نعم"}}))


def test_book_with_bad_publish_config_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="publish.clips"):
        toy(tmp_path, publish={"course": "g10-s1", "clips": "غائب"})


def test_load_builds_index_from_lessons_dir_then_loads(tmp_path, recorder, capsys):
    toy(tmp_path, load=LOAD)
    assert main([str(tmp_path), "load"]) == 0
    assert [c[0] for c in recorder.calls] == ["build_grade10_index", "load_course"]
    index_call = recorder.calls[0]
    assert index_call[index_call.index("--lessons-dir") + 1] == str(tmp_path / "lessons")
    assert recorder.calls[1] == ["load_course", "g10-s1"]
    saved = json.loads((tmp_path / "load.json").read_text(encoding="utf-8"))
    assert saved["course"] == "g10-s1" and "سطر ثانٍ" in saved["load"]
    assert '"load": "load_course: تم"' in capsys.readouterr().out  # الملخص أول سطر فقط


def test_load_without_index_only_loads(tmp_path, recorder):
    toy(tmp_path, load={"course": "g12-sci-s1"})
    assert main([str(tmp_path), "load"]) == 0
    assert recorder.calls == [["load_course", "g12-sci-s1"]]


def test_publish_passes_clips_dir(tmp_path, recorder):
    toy(tmp_path, publish=PUBLISH)
    assert main([str(tmp_path), "publish"]) == 0
    assert recorder.calls == [["publish_assets", "g10-s1", "--source", str(tmp_path / "clips")]]
    assert (tmp_path / "publish.json").exists()


def test_missing_section_and_missing_clips_dir_exit_five(tmp_path, recorder, capsys):
    toy(tmp_path)
    assert main([str(tmp_path), "publish"]) == 5
    assert "لا قسم publish" in capsys.readouterr().err
    (tmp_path / "clips" / "1.1_m1_p3.png").unlink()
    (tmp_path / "clips").rmdir()
    reload(tmp_path, publish=PUBLISH)
    assert main([str(tmp_path), "publish"]) == 5
    assert "مجلد المقاطع" in capsys.readouterr().err
    assert recorder.calls == []


def test_command_failure_exits_five_and_leaves_no_stamp(tmp_path, monkeypatch, capsys):
    toy(tmp_path, load=LOAD)
    monkeypatch.setattr(publish, "run_manage", Recorder(fail_on="load_course"))
    assert main([str(tmp_path), "load"]) == 5
    assert "فشل load_course" in capsys.readouterr().err
    assert not (tmp_path / "load.json").exists()
    stamp_file = tmp_path / ".stamps.json"
    assert not stamp_file.exists() or "load" not in json.loads(stamp_file.read_text(encoding="utf-8"))


def test_all_runs_load_before_publish_only_when_configured(tmp_path, monkeypatch):
    toy(tmp_path)
    from tools.extraction import __main__ as cli

    ran = []
    monkeypatch.setattr(cli, "run_stage", lambda book, name, force=False: ran.append(name))
    assert main([str(tmp_path), "all"]) == 0
    assert (
        ran[-1] == "lesson" and "load" not in ran and "publish" not in ran
    )  # all لا يلمس القاعدة ولا التخزين
    ran.clear()
    reload(tmp_path, load=LOAD, publish=PUBLISH)
    assert main([str(tmp_path), "all"]) == 0
    assert ran[-3:] == ["lesson", "load", "publish"]


def test_stamp_skips_unchanged_and_follows_inputs_and_target(tmp_path, recorder, monkeypatch):
    book = toy(tmp_path, load=LOAD, publish=PUBLISH)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///a.db")
    monkeypatch.setenv("ASSETS_STORAGE", "local")
    assert run_stage(book, "load") and run_stage(book, "publish")
    assert not run_stage(book, "load") and not run_stage(book, "publish")  # لم يتغير شيء: تُخطيتا
    (tmp_path / "clips" / "1.1_m2_p4.png").write_bytes(b"x")
    assert not run_stage(book, "load") and run_stage(book, "publish")  # مقطع جديد يعيد النشر وحده
    (tmp_path / "lessons" / "lesson_1_1.json").write_text('{"a": 1}', encoding="utf-8")
    assert run_stage(book, "load")  # سجل درس تغيّر يعيد التحميل
    monkeypatch.setenv("DATABASE_URL", "postgres://prod")  # وجهة أخرى: يعاد التحميل ولو لم يتغير مدخل
    assert run_stage(book, "load") and run_stage(book, "publish")
    monkeypatch.setenv("ASSETS_S3_BUCKET", "bucket")
    assert not run_stage(book, "load") and run_stage(book, "publish")  # التخزين لا يخص التحميل
    assert run_stage(book, "load", force=True)


def test_target_token_hides_values_and_separates_stages(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:سر@host/db")
    monkeypatch.setenv("ASSETS_S3_BUCKET", "b")
    token = publish.target_token("publish")
    assert "سر" not in token and len(token) == 64
    assert token != publish.target_token("load")
    monkeypatch.setenv("ASSETS_S3_BUCKET", "c")
    assert publish.target_token("publish") != token
    assert publish.target_token("load") == publish.target_token("load")


def test_stamp_digest_without_target_is_unchanged_for_other_stages(tmp_path):
    book = toy(tmp_path)
    assert stamps.digest(book, "layout") == stamps.digest(book, "layout", target="")
    assert stamps.digest(book, "load", target="a") != stamps.digest(book, "load", target="b")


def test_run_manage_reports_failure_tail(tmp_path):
    book = toy(tmp_path, django={"root": str(tmp_path)})
    with pytest.raises(publish.PublishError, match="لا manage.py"):
        publish.run_manage(book, ["load_course", "x"])
    (tmp_path / "manage.py").write_text(
        "import sys\nprint('خطأ مفصّل أول', file=sys.stderr)\nprint('آخر سطر', file=sys.stderr)\nsys.exit(3)\n",
        encoding="utf-8",
    )
    with pytest.raises(publish.PublishError, match="فشل load_course: آخر سطر"):
        publish.run_manage(book, ["load_course", "x"])
    (tmp_path / "manage.py").write_text("import sys\nprint('ok', sys.argv[1:])\n", encoding="utf-8")
    assert publish.run_manage(book, ["load_course", "x"]) == "ok ['load_course', 'x']"
