"""الوحدة غير المعتمدة في الاختبارات من التجهيز `draft_unit` وحده (conftest.py): لا ترقيع لـ `unit_prep` في ملف اختبار."""

import re
from pathlib import Path

TESTS = Path(__file__).parent
PATCH = re.compile(r"monkeypatch\.setattr\([^)]*unit_prep", re.S)


def test_only_conftest_patches_unit_prep():
    offenders = [
        p.name
        for p in TESTS.glob("test_*.py")
        if p != Path(__file__) and PATCH.search(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"استعمل التجهيز draft_unit بدل ترقيع unit_prep في: {offenders}"
    assert PATCH.search((TESTS / "conftest.py").read_text(encoding="utf-8"))
