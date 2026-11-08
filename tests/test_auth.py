import json

import pytest
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.test import Client

from apps.core.models import AuditLog
from apps.papers.access import GENERATE_PERMISSION, TEACHER_GROUP, ensure_teacher

PASSWORD = "Rasm-Bayani-2026"
EXAM = "/api/v1/papers/exam?blueprint=g12-sci-s1-2026-27-forecast&seed=1"


def post_login(client, username="teacher", password=PASSWORD, **extra):
    return client.post(
        "/api/v1/auth/login",
        json.dumps({"username": username, "password": password}),
        content_type="application/json",
        **extra,
    )


@pytest.fixture
def teacher(db):
    user, _ = ensure_teacher("teacher", PASSWORD)
    return user


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url", ["/api/v1/lessons", "/api/v1/blueprints", EXAM, "/api/v1/papers/worksheet?lesson=2.4"]
)
def test_papers_require_login(client, url):
    assert client.get(url).status_code == 401


@pytest.mark.django_db
def test_user_without_permission_is_forbidden(client, django_user_model):
    client.force_login(django_user_model.objects.create_user(username="guest", password=PASSWORD))
    assert client.get("/api/v1/lessons").status_code == 403


@pytest.mark.django_db
def test_superuser_can_generate(client, django_user_model):
    client.force_login(django_user_model.objects.create_superuser(username="root", password=PASSWORD))
    assert client.get(EXAM).status_code == 200


def test_login_session_and_logout(client, teacher):
    res = post_login(client)
    assert res.status_code == 200
    assert GENERATE_PERMISSION in res.json()["permissions"]
    assert client.get(EXAM).status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get(EXAM).status_code == 401
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"auth.login", "auth.logout"} <= actions


def test_login_rotates_session_key(client, teacher):
    client.get("/api/v1/ping")
    client.session.save()
    before = client.session.session_key
    post_login(client)
    assert client.session.session_key != before


def test_wrong_password_is_rejected_and_audited(client, teacher):
    res = post_login(client, password="wrong-password")
    assert res.status_code == 401
    assert AuditLog.objects.filter(action="auth.failed", target="teacher").exists()
    assert client.get(EXAM).status_code == 401


def test_login_requires_csrf_token(teacher):
    strict = Client(enforce_csrf_checks=True)
    assert post_login(strict).status_code == 403
    strict.get("/")
    token = strict.cookies["csrftoken"].value
    assert post_login(strict, HTTP_X_CSRFTOKEN=token).status_code == 200


def test_logout_requires_csrf_token(teacher):
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(teacher)
    assert strict.post("/api/v1/auth/logout").status_code == 403


def test_repeated_failures_lock_the_account(client, teacher, settings):
    settings.AXES_ENABLED = True
    for _ in range(settings.AXES_FAILURE_LIMIT):
        post_login(client, password="wrong-password")
    assert post_login(client).status_code == 429
    assert client.get(EXAM).status_code == 401


def test_ensure_teacher_is_idempotent(teacher):
    again, created = ensure_teacher("teacher")
    assert again.pk == teacher.pk
    assert created is False
    assert again.groups.filter(name=TEACHER_GROUP).count() == 1
    assert Group.objects.get(name=TEACHER_GROUP).permissions.count() == 1


@pytest.mark.django_db
def test_ensure_teacher_rejects_weak_or_missing_password():
    with pytest.raises(ValueError):
        ensure_teacher("nopass")
    with pytest.raises(Exception, match="."):
        ensure_teacher("weak", "12345")


@pytest.mark.django_db
def test_create_teacher_command(monkeypatch, django_user_model):
    answers = iter([PASSWORD, PASSWORD])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))
    call_command("create_teacher", "mona")
    assert django_user_model.objects.get(username="mona").has_perm(GENERATE_PERMISSION)

    answers = iter([PASSWORD, "different"])
    with pytest.raises(CommandError):
        call_command("create_teacher", "sara")


@pytest.mark.parametrize(
    ("hops", "forwarded", "expected"),
    [
        (0, "1.1.1.1", "10.0.0.1"),
        (1, "6.6.6.6, 203.0.113.9", "203.0.113.9"),
        (1, "", "10.0.0.1"),
        (1, "not-an-ip", "10.0.0.1"),
        (2, "6.6.6.6, 203.0.113.9, 100.64.0.2", "203.0.113.9"),
    ],
)
def test_client_ip_takes_trusted_hop_from_the_right(rf, settings, hops, forwarded, expected):
    from apps.core.client_ip import client_ip

    settings.TRUSTED_PROXY_COUNT = hops
    request = rf.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR=forwarded)
    assert client_ip(request) == expected


def test_lockout_by_ip_does_not_block_other_clients(client, teacher, settings, django_user_model):
    settings.AXES_ENABLED = True
    settings.TRUSTED_PROXY_COUNT = 1
    django_user_model.objects.create_user(username="other", password=PASSWORD)
    for _ in range(settings.AXES_FAILURE_LIMIT):
        post_login(client, username="other", password="wrong-password", HTTP_X_FORWARDED_FOR="198.51.100.7")
    assert post_login(Client(), HTTP_X_FORWARDED_FOR="198.51.100.7").status_code == 429
    assert post_login(Client(), HTTP_X_FORWARDED_FOR="203.0.113.9").status_code == 200
