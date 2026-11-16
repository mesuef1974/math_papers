"""عامل المهام الخلفية: تطبيق Celery يُحمَّل مع Django، والوسيط من REDIS_URL، وبلا وسيط تُنفَّذ المهمة فورًا."""

import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest
from celery.exceptions import TimeoutError as CeleryTimeoutError
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core import tasks
from config import celery_app

ROOT = Path(__file__).resolve().parent.parent


def base_settings(**env: str) -> dict[str, str]:
    """قيم CELERY_* كما يحسبها config.settings.base في عملية مستقلة ببيئة معيّنة."""
    code = (
        "import config.settings.base as s;"
        "print(s.CELERY_BROKER_URL, s.CELERY_RESULT_BACKEND, s.CELERY_TASK_ALWAYS_EAGER, sep='|')"
    )
    clean = {k: v for k, v in os.environ.items() if k not in {"REDIS_URL", "CELERY_TASK_ALWAYS_EAGER"}}
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env={**clean, "SECRET_KEY": "ci-testing-only", **env},
        capture_output=True,
        text=True,
        check=True,
    )
    broker, backend, eager = proc.stdout.strip().split("|")
    return {"broker": broker, "backend": backend, "eager": eager}


def test_ping_is_registered_on_the_project_app_and_runs():
    assert celery_app.main == "math_papers"
    assert celery_app.tasks["core.ping"].name == tasks.ping.name == "core.ping"
    assert tasks.ping.delay().get() == "pong"


def test_tests_never_need_a_broker(settings):
    assert settings.CELERY_TASK_ALWAYS_EAGER is True
    assert celery_app.conf.task_always_eager is True


def test_without_redis_tasks_run_in_place():
    assert base_settings() == {"broker": "memory://", "backend": "cache+memory://", "eager": "True"}


def test_with_redis_tasks_go_to_the_queue_unless_forced_eager():
    url = "redis://cache.invalid:6379/0"
    assert base_settings(REDIS_URL=url) == {"broker": url, "backend": url, "eager": "False"}
    assert base_settings(REDIS_URL=url, CELERY_TASK_ALWAYS_EAGER="1")["eager"] == "True"


def test_late_ack_settings_reach_the_app():
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.task_time_limit == 300


def test_worker_ping_reports_eager_mode():
    out = StringIO()
    call_command("worker_ping", stdout=out)
    assert "تنفيذ فوري" in out.getvalue()


def test_worker_ping_fails_when_no_worker_answers(settings, monkeypatch):
    class Silent:
        def get(self, timeout=None):
            raise CeleryTimeoutError()

    settings.CELERY_TASK_ALWAYS_EAGER = False
    monkeypatch.setattr(tasks.ping, "delay", lambda: Silent())
    with pytest.raises(CommandError, match="لا ردّ من العامل خلال 2 ثانية"):
        call_command("worker_ping", timeout=2)


def test_worker_ping_reports_a_live_worker(settings, monkeypatch):
    class Answer:
        def get(self, timeout=None):
            return "pong"

    settings.CELERY_TASK_ALWAYS_EAGER = False
    monkeypatch.setattr(tasks.ping, "delay", lambda: Answer())
    out = StringIO()
    call_command("worker_ping", stdout=out)
    assert "العامل يعمل: pong" in out.getvalue()


def test_worker_script_named_in_railway_toml_exists_and_refuses_to_start_without_redis():
    script = ROOT / "scripts" / "railway-worker.sh"
    assert "scripts/railway-worker.sh" in (ROOT / "railway.toml").read_text(encoding="utf-8")
    text = script.read_text(encoding="utf-8")
    assert "exec celery -A config worker" in text
    assert text.index("REDIS_URL مطلوب") < text.index("exec celery")
    assert b"\r\n" not in script.read_bytes()
