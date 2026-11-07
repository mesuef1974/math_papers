import subprocess
import sys
import time

from scripts import preview_server as ps

SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]
CHATTY = [sys.executable, "-c", "import time\nwhile True:\n    print('طلب', flush=True)\n    time.sleep(0.2)"]


def run(tmp_path, cmd, **kw):
    kw.setdefault("poll", 0.1)
    return ps.supervise(cmd, log_path=tmp_path / "s.log", pid_path=tmp_path / "s.pid", **kw)


def test_idle_child_is_closed_by_ttl(tmp_path):
    started = time.monotonic()
    assert run(tmp_path, SLEEPER, ttl=0.6, max_life=30) == "idle"
    assert time.monotonic() - started < 10
    assert not (tmp_path / "s.pid").exists()


def test_activity_keeps_it_alive_until_max_life(tmp_path):
    assert run(tmp_path, CHATTY, ttl=1.0, max_life=2.0) == "max_life"


def test_child_that_exits_ends_supervision(tmp_path):
    assert run(tmp_path, [sys.executable, "-c", "pass"], ttl=30, max_life=30) == "exited"


def test_child_process_is_really_dead_after_close(tmp_path):
    seen = {}
    original = ps.kill_tree

    def spy(pid):
        seen["pid"] = pid
        original(pid)

    ps.kill_tree = spy
    try:
        run(tmp_path, SLEEPER, ttl=0.4, max_life=30)
    finally:
        ps.kill_tree = original
    time.sleep(0.5)
    assert not ps.alive(seen["pid"])


def test_stop_closes_a_running_server_from_pid_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "STATE_DIR", tmp_path)
    pid_path, _ = ps.state_paths(59999)
    child = subprocess.Popen(SLEEPER)  # noqa: S603
    pid_path.write_text(str(child.pid))
    assert ps.stop(59999) is True
    assert child.wait(timeout=10) is not None
    assert not pid_path.exists()
    assert ps.stop(59999) is False


def test_running_reflects_pid_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "STATE_DIR", tmp_path)
    pid_path, _ = ps.state_paths(59998)
    assert ps.running(59998) is False
    child = subprocess.Popen(SLEEPER)  # noqa: S603
    try:
        pid_path.write_text(str(child.pid))
        assert ps.running(59998) is True
    finally:
        ps.kill_tree(child.pid)
        child.wait(timeout=10)
    assert ps.running(59998) is False


def test_running_true_when_port_is_busy_without_pid_file(tmp_path, monkeypatch):
    import socket

    monkeypatch.setattr(ps, "STATE_DIR", tmp_path)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        assert ps.running(sock.getsockname()[1]) is True
