"""مسارات الحزمة العلاجية (M2.3): المعلم ينزّل حزمة شعبته، 401 و403 و503، ورسائل PlanningError تصله."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client

from apps.core.models import AuditLog
from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import Lesson
from apps.papers import pdf
from apps.papers.access import ensure_teacher
from apps.papers.domain import item_bank
from apps.planning import services
from apps.planning.models import ItemResult, SectionStudent

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("loaded_courses")]

SECTION = "10/3"
URL = f"/api/v1/remedial-packs/{GRADE10_SLUG}/1.1"
PASSWORD = "Rasm-Bayani-2026"  # pragma: allowlist secret
PRIVATE = ("سالم", "المري", "1001")


@pytest.fixture(autouse=True)
def rendered(monkeypatch):
    cache.clear()
    calls: list[dict] = []

    def render(payload):
        calls.append(payload)
        return b"%PDF-1.7 pack"

    monkeypatch.setattr(pdf, "render_payload", render)
    yield calls
    cache.clear()


@pytest.fixture
def teacher(teacher_client):
    return get_user_model().objects.get(username="teacher")


def enroll(owner, wrong: bool = True) -> None:
    student = SectionStudent.objects.create(
        owner=owner, section=SECTION, enrollment_no="1001", first_name="سالم", last_name="المري"
    )
    ItemResult.objects.create(
        student=student,
        lesson=Lesson.objects.get(course__slug=GRADE10_SLUG, code="1.1"),
        example=item_bank.exit_ticket(GRADE10_SLUG, "1.1", 1).example,
        seed=0,
        choice=0,
        correct=not wrong,
        error_kind="sign" if wrong else "",
    )


def post(client, section: str = SECTION):
    return client.post(URL, json.dumps({"section": section}), content_type="application/json")


def test_teacher_requests_and_downloads_the_pack(teacher_client, teacher, rendered):
    enroll(teacher)
    assert teacher_client.get(URL, {"section": SECTION}).json() == {"status": "idle", "detail": ""}
    assert teacher_client.get(f"{URL}/download", {"section": SECTION}).status_code == 404

    assert post(teacher_client).json() == {"status": "ready", "detail": ""}
    assert teacher_client.get(URL, {"section": SECTION}).json()["status"] == "ready"
    # مفتاح تخزين من العميل يُهمل
    response = teacher_client.get(f"{URL}/download", {"section": SECTION, "key": "assets/x"})
    assert response.status_code == 200 and response.content == b"%PDF-1.7 pack"
    assert response["Content-Type"] == "application/pdf" and response["Cache-Control"] == "private, no-store"
    assert response["Content-Disposition"] == f'attachment; filename="remedial-{GRADE10_SLUG}-1.1.pdf"'
    assert len(rendered) == 1

    logs = AuditLog.objects.filter(action__startswith="remedial.")
    assert {"remedial.pack.request", "remedial.pack.build", "remedial.pack.download"} <= {
        log.action for log in logs
    }
    logged = json.dumps(list(logs.values("target", "payload")), ensure_ascii=False)
    assert not any(private in logged for private in PRIVATE)


def test_requires_session_and_teacher_permission(outsider_client):
    for client, status in ((Client(), 401), (outsider_client, 403)):
        assert post(client).status_code == status
        assert client.get(URL, {"section": SECTION}).status_code == status
        assert client.get(f"{URL}/download", {"section": SECTION}).status_code == status


def test_other_teacher_gets_403(teacher_client, teacher, rendered):
    enroll(teacher)
    post(teacher_client)
    other = Client()
    other.force_login(ensure_teacher("teacher2", PASSWORD)[0])
    assert post(other).status_code == 403
    assert other.get(URL, {"section": SECTION}).status_code == 403
    assert other.get(f"{URL}/download", {"section": SECTION}).status_code == 403
    assert len(rendered) == 1
    assert AuditLog.objects.filter(action="remedial.pack.denied").count() == 3


@pytest.mark.parametrize(("redis_url", "eager"), [("", True), ("redis://x", True), ("", False)])
def test_production_without_broker_is_503(
    teacher_client, teacher, rendered, settings, monkeypatch, redis_url, eager
):
    enroll(teacher)
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.production")
    settings.DEBUG = False
    settings.REDIS_URL = redis_url
    settings.CELERY_TASK_ALWAYS_EAGER = eager
    for response in (post(teacher_client), teacher_client.get(URL, {"section": SECTION})):
        assert response.status_code == 503 and "Redis" in response.json()["detail"]
    assert rendered == []


def test_production_with_broker_queues_once(teacher_client, teacher, settings, monkeypatch):
    from apps.planning.tasks import build_class_pack_task

    enroll(teacher)
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.production")
    settings.DEBUG = False
    settings.REDIS_URL, settings.CELERY_TASK_ALWAYS_EAGER = "redis://x", False
    queued: list[tuple] = []
    monkeypatch.setattr(build_class_pack_task, "delay", lambda *args: queued.append(args))
    building = {"status": "pending", "detail": "الحزمة قيد البناء"}
    assert post(teacher_client).json() == building
    assert post(teacher_client).json() == building
    assert queued == [(teacher.pk, GRADE10_SLUG, "1.1", SECTION)]
    assert teacher_client.get(f"{URL}/download", {"section": SECTION}).status_code == 404


def test_planning_errors_reach_the_teacher(teacher_client, teacher, monkeypatch):
    enroll(teacher, wrong=False)
    out = post(teacher_client).json()
    assert out == {"status": "failed", "detail": "لا أخطاء في هذا الدرس تُبنى منها أوراق علاجية"}

    message = f"الحزمة تتسع لـ {services.MAX_PACK_STUDENTS} طالبًا"

    def too_many(*args):
        raise services.PlanningError(message)

    monkeypatch.setattr(services, "class_pack_payload", too_many)
    assert post(teacher_client).json() == {"status": "failed", "detail": message}


def test_render_failure_is_a_generic_message(teacher_client, teacher, monkeypatch, caplog):
    enroll(teacher)
    post(teacher_client)  # حزمة سابقة سليمة
    SectionStudent.objects.update(first_name="سالمان")  # تغيّرت المدخلات فيعاد البناء

    def broken(payload):
        raise RuntimeError("سالم 1001")

    monkeypatch.setattr(pdf, "render_payload", broken)
    assert post(teacher_client).json() == {"status": "failed", "detail": "تعذّر بناء الحزمة"}
    # لا تُقدَّم الحزمة السابقة بعد فشل إعادة البناء
    assert teacher_client.get(f"{URL}/download", {"section": SECTION}).status_code == 404
    # لا رسالة استثناء في السجل: النوع وحده
    assert "RuntimeError" in caplog.text
    assert not any(private in caplog.text for private in PRIVATE)


def test_failure_before_the_build_does_not_stay_pending(teacher):
    from apps.planning.tasks import build_class_pack_task

    scope = (teacher.pk + 999, GRADE10_SLUG, "1.1", SECTION)
    services.start_class_pack(*scope)
    with pytest.raises(services.PackBuildError):
        build_class_pack_task(*scope)
    assert services.class_pack_state(*scope) == ("failed", services.PACK_FAILED)
