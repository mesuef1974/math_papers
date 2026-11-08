"""تصليب المرحلة 0: معرّف الطلب من الخادم، التوثيق للطاقم، تحديد المعدل، ترويسات الأمن، مخطط الأخطاء، هوية الأجزاء."""

import json
import random

import pytest
from ninja.throttling import UserRateThrottle

from apps.core.models import AuditLog
from apps.papers.access import ensure_teacher
from apps.papers.domain.generators import REGISTRY, ExhaustedError, generate, generator_version

PASSWORD = "Rasm-Bayani-2026"
SLUG = "g12-sci-s1-2026-27-forecast"


def login(client, password, **extra):
    return client.post(
        "/api/v1/auth/login",
        json.dumps({"username": "teacher", "password": password}),
        content_type="application/json",
        **extra,
    )


@pytest.fixture
def teacher(db):
    user, _ = ensure_teacher("teacher", PASSWORD)
    client_id = user.pk
    return user, client_id


@pytest.fixture
def teacher_client(client, teacher):
    client.force_login(teacher[0])
    return client


def test_client_request_id_cannot_collapse_audit_rows(client, teacher):
    """ترويسة X-Request-ID الثابتة من العميل كانت تجعل الفشل الثاني لا يُسجَّل."""
    for _ in range(3):
        res = login(client, "wrong-password", HTTP_X_REQUEST_ID="fixed-by-attacker")
        assert res.status_code == 401
        assert res["X-Request-ID"] != "fixed-by-attacker"
    assert AuditLog.objects.filter(action="auth.failed", target="teacher").count() == 3
    ids = set(AuditLog.objects.filter(action="auth.failed").values_list("request_id", flat=True))
    assert len(ids) == 3 and all(len(value) == 32 for value in ids)


@pytest.mark.django_db
def test_api_docs_are_for_staff_only(client, staff_user):
    assert client.get("/api/v1/docs/").status_code == 302
    assert client.get("/api/v1/openapi.json").status_code == 302
    client.force_login(staff_user)
    assert client.get("/api/v1/openapi.json").status_code == 200


@pytest.mark.django_db
def test_security_headers_on_shell_and_api(client):
    for url in ("/", "/api/v1/ping"):
        res = client.get(url)
        csp = res["Content-Security-Policy"]
        assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
        assert "camera=()" in res["Permissions-Policy"]


def test_user_rate_throttle_blocks_after_limit(rf, teacher):
    from django.core.cache import cache

    cache.clear()  # سجل المعدل مشترك في الكاش مع طلبات الاختبارات السابقة للمستخدم نفسه
    throttle = UserRateThrottle("2/m")
    request = rf.get("/api/v1/lessons")
    request.user = teacher[0]
    assert throttle.allow_request(request) is True
    assert throttle.allow_request(request) is True
    assert throttle.allow_request(request) is False


def test_papers_router_is_throttled_per_user():
    from apps.papers.api import router

    assert any(isinstance(t, UserRateThrottle) for t in router.throttle)


def test_exhausted_generation_is_409_not_500(teacher_client, monkeypatch):
    from apps.papers import services

    def boom(*args, **kwargs):
        raise ExhaustedError("x")

    monkeypatch.setattr(services, "generate", boom)
    res = teacher_client.get("/api/v1/papers/worksheet", {"lesson": "2.4", "count": 3, "seed": 1})
    assert res.status_code == 409
    assert "رقم النموذج" in res.json()["detail"]


def test_validation_errors_are_arabic_with_details(teacher_client):
    res = teacher_client.get("/api/v1/papers/worksheet", {"lesson": "2.4", "count": 500})
    assert res.status_code == 422
    body = res.json()
    assert body["detail"].startswith("مدخلات غير صالحة") and body["errors"]


@pytest.mark.django_db
def test_audit_limit_must_be_positive(client, staff_user):
    client.force_login(staff_user)
    assert client.get("/api/v1/audit", {"limit": 0}).status_code == 422
    assert client.get("/api/v1/audit", {"limit": 1}).status_code == 200


def test_paper_carries_identity_for_saving_and_replacing(teacher_client):
    data = teacher_client.get("/api/v1/papers/exam", {"blueprint": SLUG, "seed": 7}).json()
    assert data["kind"] == "exam" and data["blueprint"] == SLUG and data["lesson_code"] == ""
    assert data["generator_version"] == generator_version() and len(data["generator_version"]) == 12
    parts = [part for q in data["questions"] for part in q["parts"]]
    assert all(part["variant"] and len(part["fingerprint"]) == 12 for part in parts)
    assert len({part["fingerprint"] for part in parts}) == len(parts)
    assert all(
        part["slot"]["kind"] in {"mcq", "essay"} and part["slot"]["level"] in {"K", "A", "R"}
        for part in parts
    )
    sheet = teacher_client.get(
        "/api/v1/papers/worksheet", {"lesson": "2.4", "count": 2, "seed": 1, "level": "A"}
    ).json()
    assert sheet["kind"] == "worksheet" and sheet["lesson_code"] == "2.4"
    assert sheet["questions"][0]["parts"][0]["slot"] == {"kind": "essay", "level": "A", "needs_graph": False}


def test_generate_can_be_pinned_to_a_variant():
    name = REGISTRY["2.4"][0].__name__
    problem = generate("2.4", random.Random(3), variant_name=name)
    assert problem.variant == name
    other = generate("2.4", random.Random(4), variant_name=name)
    assert other.variant == name and other.fingerprint != problem.fingerprint


def test_generator_version_is_stable_and_changes_with_registry():
    before = generator_version()
    assert before == generator_version()
    REGISTRY.setdefault("9.9", []).append(lambda rng: None)
    try:
        assert generator_version() != before
    finally:
        del REGISTRY["9.9"]
