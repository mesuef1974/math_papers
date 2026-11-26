import pytest

from apps.core.models import BoardSnapshot

pytestmark = pytest.mark.django_db

PUSH = "/api/v1/automation/snapshot"
BOARD = "/api/v1/automation/board"
CARD = {"id": "20261126-abc123", "title": "بطاقة", "group": "running", "at_stage": 1}
PAYLOAD = {"stages": ["في الطابور", "البرمجة"], "cards": [CARD], "pulse": {"text": "نبض", "warn": False}}


def push(client, token, payload=PAYLOAD):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return client.post(PUSH, payload, content_type="application/json", **headers)


@pytest.mark.parametrize(("configured", "sent"), [("s3cret", None), ("s3cret", "wrong"), ("", "anything")])
def test_push_refused_without_the_configured_key(client, settings, configured, sent):
    settings.BOARD_PUSH_TOKEN = configured
    assert push(client, sent).status_code == 401
    assert not BoardSnapshot.objects.exists()


def test_push_replaces_single_row_and_superuser_reads_it(client, settings, admin_user):
    settings.BOARD_PUSH_TOKEN = "s3cret"
    assert push(client, "s3cret", PAYLOAD | {"cards": []}).status_code == 204
    assert push(client, "s3cret").status_code == 204
    assert BoardSnapshot.objects.count() == 1
    client.force_login(admin_user)
    body = client.get(BOARD).json()
    assert body["received_at"]
    assert body["board"]["cards"][0]["id"] == CARD["id"]


def test_foreign_link_rejected(client, settings):
    settings.BOARD_PUSH_TOKEN = "s3cret"
    bad = PAYLOAD | {"cards": [CARD | {"url": "javascript:alert(1)"}]}
    assert push(client, "s3cret", bad).status_code == 422


def test_board_is_for_superuser_only(client, django_user_model):
    assert client.get(BOARD).status_code == 401
    client.force_login(django_user_model.objects.create_user("staff", password="x", is_staff=True))
    assert client.get(BOARD).status_code == 403


def test_empty_board(client, admin_user):
    client.force_login(admin_user)
    assert client.get(BOARD).json() == {"received_at": None, "board": None}
