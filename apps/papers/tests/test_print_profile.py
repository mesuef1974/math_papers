import json

import pytest

from apps.core.models import AuditLog
from apps.papers.models import DEFAULT_EXAM_MINUTES, PrintProfile


def put(client, body):
    return client.put("/api/v1/print-profile", json.dumps(body), content_type="application/json")


@pytest.mark.django_db
def test_defaults_without_a_saved_profile(client):
    data = client.get("/api/v1/print-profile").json()
    assert data["exam_minutes"] == DEFAULT_EXAM_MINUTES == 150
    assert data["subject"] == "الرياضيات" and data["school"] == ""
    assert PrintProfile.objects.count() == 0  # القراءة لا تكتب


@pytest.mark.django_db
def test_save_is_idempotent_and_audited(client):
    body = {
        "school": "  مدرسة قطر الثانوية ",
        "teacher_name": "أ. سعيد",
        "subject": "الرياضيات",
        "grade": "الصف 12 علمي",
        "exam_minutes": 120,
        "exam_instructions": "أجب عن كل الأسئلة",
        "worksheet_instructions": "",
    }
    first = put(client, body)
    assert first.status_code == 200 and first.json()["school"] == "مدرسة قطر الثانوية"
    assert put(client, body).status_code == 200
    assert PrintProfile.objects.count() == 1
    assert AuditLog.objects.filter(action="print_profile.save").count() == 1
    assert client.get("/api/v1/print-profile").json()["exam_minutes"] == 120


@pytest.mark.django_db
def test_rejects_out_of_range_duration(client):
    res = put(client, {"subject": "الرياضيات", "exam_minutes": 5})
    assert res.status_code == 422


@pytest.mark.django_db
def test_profile_is_per_teacher(client, django_user_model):
    put(client, {"subject": "الرياضيات", "exam_minutes": 90, "school": "أ"})
    other = django_user_model.objects.create_superuser(username="other", password="Rasm-Bayani-2026")
    client.force_login(other)
    assert client.get("/api/v1/print-profile").json()["school"] == ""
