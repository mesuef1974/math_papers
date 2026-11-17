"""مراحل الرؤية وعميل llama: جواب مختلق وصور اصطناعية، بلا نموذج ولا خادم حقيقي."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import yaml

from tools.extraction import llama, reps, vision
from tools.extraction.__main__ import main

from .conftest import TOY_PAGES, make_book

Q = vision.QUESTIONS


def toy(tmp_path, **over):
    dirs = {"vision": "vision", "badges": "badges", "crops": "crops", "vocab": "vocab", "render": "render"}
    book = make_book(tmp_path, TOY_PAGES, dirs=dirs, **over)
    layout = {"lessons": [{"id": "1.1", "pages_pdf": [3, 5]}, {"id": "1.2", "pages_pdf": [7, 8]}]}
    (tmp_path / "layout.json").write_text(json.dumps(layout), encoding="utf-8")
    return book


def png(root, n, size=(100, 100), color=(255, 255, 255)):
    from PIL import Image

    (root / "render").mkdir(exist_ok=True)
    Image.new("RGB", size, color).save(root / "render" / f"{n:04d}.png")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_pages_keeps_exercises_in_range_and_mp_codes_and_resumes(tmp_path):
    book = toy(tmp_path)
    (tmp_path / "render").mkdir()
    for n in (1, 2):
        (tmp_path / "render" / f"{n:04d}.png").write_bytes(b"x")
    calls = []

    def ask(image, question, fmt):
        calls.append((image.stem, question))
        return {
            Q["examples"]: {"numbers": [1, 2]},
            Q["exercises"]: {"numbers": [5, 0, 120, 3, 5]},
            Q["practices"]: {"items": [" MP.1 ", "نص", "MP.7"]},
        }[question]

    assert vision.run_pages(book, ask, 1, 3) == {"pages": 2}  # الصفحة 3 بلا صورة مصيَّرة فتُتخطى
    assert read(tmp_path / "vision" / "0001.json") == {
        "examples": [1, 2],
        "exercises": [3, 5],
        "practices": ["MP.1", "MP.7"],
    }
    assert vision.run_pages(book, ask, 1, 3) == {"pages": 0}
    assert len(calls) == 6  # ثلاثة أسئلة لكل صفحة، ولا إعادة


def test_question_override_and_model_size(tmp_path):
    book = toy(tmp_path, vision={"questions": {"examples": "سؤال بديل"}, "models_for": {"pages": "large"}})
    assert vision.text(book, "examples") == "سؤال بديل" and vision.text(book, "heading") == Q["heading"]
    assert vision.model_size(book, "pages") == "large" and vision.model_size(book, "reps") == "large"
    assert vision.model_size(book, "vocab") == "small"


def test_vocab_falls_back_to_flat_question_on_empty_reply(tmp_path):
    pytest.importorskip("PIL")
    book = toy(tmp_path, vision={"vocab": {"card_box": [0, 0, 50, 40]}})
    png(tmp_path, 3)
    png(tmp_path, 7)
    pair = {"ar": "دالة", "en": "function"}

    def ask(image, question, fmt):
        if question == Q["card"]:
            return {"review": [pair], "new": []} if image.stem == "0003" else {"review": [], "new": []}
        return {"terms": [pair, pair]}

    assert vision.run_vocab(book, ask) == {"pages": 2, "terms": 3}
    assert read(tmp_path / "vocab" / "0003.json") == {"review": [pair], "new": [], "flat": []}
    assert read(tmp_path / "vocab" / "0007.json")["flat"] == [pair, pair]
    from PIL import Image

    assert Image.open(tmp_path / "vocab" / "crops" / "0003.png").size == (50, 40)
    assert vision.run_vocab(book, ask, [3]) == {"pages": 0, "terms": 0}


def test_examples_crops_each_badge_and_asks_reps_on_thumbnail(tmp_path):
    np = pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image")
    book = toy(tmp_path)
    badge = reps.CONTINUATION_DEFAULTS["badge"]
    arr = np.full((2000, 1000, 3), 255, dtype=np.uint8)
    for y in (300, 1000):
        arr[y : y + 40, 880:930] = badge  # شارتا العمود الأيمن (عرضها 0.87-0.94)
        arr[y : y + 20, 300:380] = badge  # شارتا المصغّرة (0.28-0.40)
    (tmp_path / "render").mkdir()
    Image.fromarray(arr).save(tmp_path / "render" / "0003.png")
    seen = []

    def ask(image, question, fmt):
        seen.append(image.name)
        if question == Q["heading"]:
            return {"n": 1 if "0003_0" in image.name else 2, "title": " عنوان ", "focus": ""}
        return {"yes": question in (reps.question(book, "table"), reps.question(book, "context"))}

    assert vision.run_examples(book, ask) == {"pages": 1, "examples": 2}
    found = read(tmp_path / "badges" / "0003.json")
    assert [(x["n"], x["title"], x["paired"]) for x in found] == [(1, "عنوان", True), (2, "عنوان", True)]
    assert found[0]["representations"] == ["جدول", "سياق حياتي"]
    assert sorted(p.name for p in (tmp_path / "crops").iterdir()) == [
        "0003_0_head.png",
        "0003_0_thumb.png",
        "0003_1_head.png",
        "0003_1_thumb.png",
    ]
    assert Image.open(tmp_path / "crops" / "0003_0_thumb.png").size[0] == 440  # من 0.06 إلى 0.50 من العرض
    assert vision.run_examples(book, ask)["pages"] == 0
    assert vision.run_examples(book, ask, ["9.9"])["pages"] == 0  # درس غير موجود


def test_examples_unpaired_when_badge_counts_differ(tmp_path):
    np = pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image")
    book = toy(tmp_path)
    arr = np.full((1000, 1000, 3), 255, dtype=np.uint8)
    arr[300:340, 880:930] = reps.CONTINUATION_DEFAULTS["badge"]  # شارة يمين بلا مصغّرة
    (tmp_path / "render").mkdir()
    Image.fromarray(arr).save(tmp_path / "render" / "0003.png")
    vision.run_examples(book, lambda i, q, f: {"n": 4, "title": "", "focus": ""})
    assert read(tmp_path / "badges" / "0003.json") == [
        {"n": 4, "title": "", "focus": "", "representations": None, "paired": False}
    ]


def test_command_uses_model_pair_context_and_overrides(tmp_path):
    book = toy(
        tmp_path,
        vision={"engine": "E.exe", "models_dir": "M", "port": 9000, "contexts": {"large": 4096},
                "models": {"large": {"model": "a.gguf", "mmproj": "b.gguf"}}},
    )  # fmt: skip
    cfg = llama.settings(book)
    cmd = llama.command(cfg, "large")
    assert cmd[0] == "E.exe" and cmd[cmd.index("-c") + 1] == "4096" and cmd[cmd.index("--port") + 1] == "9000"
    assert cmd[cmd.index("-m") + 1].endswith("a.gguf") and cmd[cmd.index("--mmproj") + 1].endswith("b.gguf")
    small = llama.command(cfg, "small")
    assert small[small.index("-c") + 1] == "16384" and "Qwen3VL-4B" in small[small.index("-m") + 1]
    with pytest.raises(KeyError):
        llama.command(cfg, "huge")


def test_asker_posts_image_question_and_schema_to_server(tmp_path):
    got = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            got["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            content = (
                "ليس JSON" if got["body"]["messages"][0]["content"][1]["text"] == "بدّل" else '{"yes": true}'
            )
            payload = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *a):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        server = llama.Server(httpd.server_port, ttl=60, max_life=60)
        image = tmp_path / "i.png"
        image.write_bytes(b"abc")
        ask = llama.asker(server)
        assert ask(image, "سؤال", reps.YES_NO) == {"yes": True}
        body = got["body"]
        assert body["temperature"] == 0 and body["response_format"] == reps.YES_NO and body["stream"] is False
        assert body["messages"][0]["content"][0]["image_url"]["url"].startswith("data:image/png;base64,YWJj")
        assert ask(image, "بدّل", reps.YES_NO) == {}  # جواب غير JSON
    finally:
        httpd.shutdown()


def test_cli_reports_missing_engine_with_exit_four(tmp_path, capsys):
    toy(tmp_path, vision={"engine": str(tmp_path / "no" / "llama-server.exe")})
    assert main([str(tmp_path), "vision_pages"]) == 4
    assert "تعذّر تشغيل الرؤية" in capsys.readouterr().err


def test_cli_vision_stages_are_known_and_validation_catches_bad_reps(tmp_path):
    toy(tmp_path)
    cfg = yaml.safe_load((tmp_path / "book.yaml").read_text(encoding="utf-8"))
    cfg["reps"] = {
        "passes": [{"kind": "add", "src": "ghost", "dst": "vision", "questions": {"أ": ["table"]}}]
    }
    (tmp_path / "book.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    assert main([str(tmp_path), "reps"]) == 2
