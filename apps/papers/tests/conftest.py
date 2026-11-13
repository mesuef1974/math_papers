import pytest

from apps.papers import pdf
from apps.papers.access import ensure_teacher


@pytest.fixture
def client(client, db):
    """كل مسارات الأوراق للمعلمين: العميل الافتراضي هنا معلم مسجّل."""
    teacher, _ = ensure_teacher("teacher", "Rasm-Bayani-2026")
    client.force_login(teacher)
    return client


@pytest.fixture(autouse=True)
def export_jobs_finish_with_their_test():
    """مهام التصدير (PDF وWord) تعمل في خيط خلفي واحد. اختبار ينشئ مهمة ولا ينتظرها يتركها تكتب حالتها وملفها
    في الكاش أثناء اختبار لاحق، فيفشل ذاك بحسب التوقيت. ننتظر فراغ الخيط بعد كل اختبار."""
    yield
    pdf._executor.submit(lambda: None).result(timeout=60)
