"""مسارات باقة الحصة (المرحلة 3): المعلم يطلبها وينزّلها ملفًا مضغوطًا، والبناء idempotent، وتغيّر التحضير يجعلها قديمة."""

import io
import zipfile

import pytest
from django.core.cache import cache
from django.test import Client

from apps.core.models import AuditLog
from apps.curriculum.courses import GRADE10_SLUG
from apps.papers import pdf
from apps.planning import package_build
from apps.planning.models import Assignment

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("loaded_courses", "local_store")]

URL = f"/api/v1/preps/{GRADE10_SLUG}/1.1/2/package"


@pytest.fixture(autouse=True)
def rendered(monkeypatch):
    cache.clear()
    calls: list[dict] = []

    def render(payload):
        calls.append(payload)
        return b"%PDF-1.7 sheet"

    monkeypatch.setattr(pdf, "render_payload", render)
    yield calls
    cache.clear()


def test_teacher_builds_and_downloads_the_package(teacher_client, rendered, monkeypatch):
    before = teacher_client.get(URL).json()
    assert before["status"] == "idle" and before["sheets"]
    assert teacher_client.get(f"{URL}/download").status_code == 404

    assert teacher_client.post(URL).json()["status"] == "ready"
    response = teacher_client.get(f"{URL}/download")
    assert response.status_code == 200 and response["Content-Type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert package_build.INDEX_NAME in names and package_build.KEY_NAME in names
    assert sum(n.endswith(".pdf") for n in names) == len(before["sheets"]) + 1
    assert any(n.endswith(".docx") for n in names)
    parts = [call["package"]["part"] for call in rendered]
    assert parts == ["sheets"] * len(before["sheets"]) + ["key"]
    assert Assignment.objects.count() == len(before["sheets"])

    # الطلب الثاني لا يعيد البناء
    teacher_client.post(URL)
    assert len(rendered) == len(parts)
    actions = set(AuditLog.objects.filter(action__startswith="package.").values_list("action", flat=True))
    assert {"package.request", "package.build", "package.download"} <= actions

    # تغيّر ما تُبنى منه يجعلها قديمة
    monkeypatch.setattr(package_build, "prep_digest", lambda prep: "changed")
    assert teacher_client.get(URL).json()["status"] == "stale"


def test_build_failure_reaches_the_teacher_and_a_retry_works(teacher_client, monkeypatch):
    def broken(payload):
        raise RuntimeError("net::ERR_CONNECTION_REFUSED at http://localhost:8000/print/secret-token")

    monkeypatch.setattr(pdf, "render_payload", broken)
    detail = teacher_client.post(URL).json()["detail"]
    assert detail == f"{package_build.FAILED} في مرحلة طباعة PDF (RuntimeError net::ERR_CONNECTION_REFUSED)"
    assert "secret-token" not in detail
    monkeypatch.setattr(pdf, "render_payload", lambda payload: b"%PDF-1.7")
    assert teacher_client.post(URL).json()["status"] == "ready"


def test_requires_session_and_teacher_permission(outsider_client):
    assert Client().post(URL).status_code == 401
    assert outsider_client.post(URL).status_code == 403


def test_unknown_period_and_missing_worker(teacher_client, monkeypatch):
    assert teacher_client.get(f"/api/v1/preps/{GRADE10_SLUG}/9.9/1/package").status_code == 404
    monkeypatch.setattr("apps.planning.services.class_pack_available", lambda: False)
    assert teacher_client.post(URL).status_code == 503
