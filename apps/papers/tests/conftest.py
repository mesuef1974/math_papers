import pytest

from apps.papers.access import ensure_teacher


@pytest.fixture
def client(client, db):
    """كل مسارات الأوراق للمعلمين: العميل الافتراضي هنا معلم مسجّل."""
    teacher, _ = ensure_teacher("teacher", "Rasm-Bayani-2026")
    client.force_login(teacher)
    return client
