import json

from automation import publish

ROW = {
    "id": "c1",
    "title": "ع" * 400,
    "group": "done",
    "at_stage": 5,
    "age": "1 د",
    "url": "",
    "note": "",
    "since": 1,
}


def snap(*done):
    groups = {"running": [], "approval": [], "queued": [], "stuck": [], "done": list(done), "backlog": []}
    return {"groups": groups, "pulse": {"text": "نبض", "warn": False}}


def test_payload_is_json_and_newest_done_first():
    out = publish.payload(snap(ROW | {"id": "old", "since": 9}, ROW))
    json.dumps(out)
    assert [card["id"] for card in out["cards"]] == ["c1", "old"]
    assert len(out["cards"][0]["title"]) == 300


def test_send_is_silent_without_configuration(monkeypatch):
    calls = []
    monkeypatch.delenv("BOARD_PUSH_URL", raising=False)
    monkeypatch.setattr(publish.urllib.request, "urlopen", lambda *a, **k: calls.append(a))
    assert publish.send() == ""
    assert not calls


def test_send_refuses_plain_http(monkeypatch):
    monkeypatch.setenv("BOARD_PUSH_URL", "http://example.test/x")
    monkeypatch.setenv("BOARD_PUSH_TOKEN", "k")
    assert "https" in publish.send()


def test_send_failure_never_leaks_the_key(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("k-secret")

    monkeypatch.setenv("BOARD_PUSH_URL", "https://example.test/x")
    monkeypatch.setenv("BOARD_PUSH_TOKEN", "k-secret")
    monkeypatch.setattr(publish.board, "snapshot", lambda **k: snap())
    monkeypatch.setattr(publish, "open_prs", lambda: None)
    monkeypatch.setattr(publish.urllib.request, "urlopen", boom)
    assert publish.send() == "تعذّر إرسال اللوحة (OSError)"
