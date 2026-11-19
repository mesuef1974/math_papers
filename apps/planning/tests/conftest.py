"""تجهيزات اختبارات التخطيط.

- مشتركة مع اختبارات الأصول: تخزين محلي مؤقت لكل اختبار (تلقائي) وعملاء المعلم والغريب.
- `draft_unit`: المصدر الوحيد لوحدة غير معتمدة في الاختبار. ملفات أهداف العاشر تُعتمد تباعًا، فلا يعتمد اختبار
  على حالة ملف حقيقي، ولا يرقّع اختبار `unit_prep` بنفسه (يحرسه `test_draft_unit_guard.py`).
"""

import pytest

from apps.assets.tests.conftest import local_store, outsider_client, teacher_client  # noqa: F401
from apps.planning import selectors

DRAFT_UNIT = 2  # وحدة لها ملف أهداف وحصص في الخطة؛ تُقرأ مسودةً في الاختبار الذي يطلب التجهيز


@pytest.fixture
def draft_unit(monkeypatch) -> int:
    """يقرأ المحددات ملف الوحدة DRAFT_UNIT مسودةً بلا اعتماد، وبقية الوحدات كما في ملفاتها؛ يعيد رقم الوحدة."""
    real = selectors.unit_prep

    def as_draft(course, unit, *args, **kwargs):
        prep = real(course, unit, *args, **kwargs)
        if prep is None or unit != DRAFT_UNIT:
            return prep
        return prep.model_copy(update={"status": "draft", "approval": None})

    monkeypatch.setattr(selectors, "unit_prep", as_draft)
    return DRAFT_UNIT
