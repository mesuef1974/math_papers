"""إعادة توليد أوراق قبل مقرر-الدرس: البصمات مثبتة من الشيفرة السابقة للمرحلة 1، فأي انزياح في البذرة أو الصيغ يكسرها."""

import hashlib
import json
from pathlib import Path

import pytest
from django.core.cache import cache

from apps.papers import services
from apps.papers.domain.generators import available_lessons, generator_version

GOLDEN = Path(__file__).with_name("golden_papers.json")
SLUG = "g12-sci-s1-2026-27-forecast"
SEED = 20261116


def without_display(value):
    """نسخة بلا مفتاح source في أي جزء."""
    if isinstance(value, dict):
        return {k: without_display(v) for k, v in value.items() if k != "source"}
    if isinstance(value, list):
        return [without_display(v) for v in value]
    return value


def digest(paper: dict) -> int:
    """أول 64 بتًا من SHA-1 رقمًا عشريًا: كاشف الأسرار يعدّ السداسي العشري الطويل سرًّا.
    سطر الصف (grade) ومصدر الجزء في الكتاب (source، من رقم مثال الصيغة) حقلا عرض أُضيفا بعد التثبيت ولا يمسّان
    المسائل، فلا يدخلان البصمة."""
    text = json.dumps(
        without_display({k: v for k, v in paper.items() if k != "grade"}),
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return int(hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest()[:16], 16)


def current_digests() -> dict[str, int]:
    cache.clear()
    result = {"generator_version": int(generator_version()[:16], 16)}
    result["exam:A"] = digest(services.build_exam(SLUG, SEED, "A"))
    result["exam:B"] = digest(services.build_exam(SLUG, SEED, "B"))
    for code in sorted(available_lessons()):
        result[f"worksheet:{code}"] = digest(services.build_worksheet(code, 6, SEED))
        result[f"worksheet-B:{code}"] = digest(services.build_worksheet(code, 6, SEED, form="B"))
        result[f"quiz:{code}"] = digest(services.build_quiz([code], SEED))
        result[f"bundle:{code}"] = digest(services.build_bundle_item(SLUG, code, SEED))
    return result


@pytest.mark.django_db
def test_papers_regenerate_identically_after_course_keys(monkeypatch):
    # توزيع مواضع الإجابة (بعد التثبيت) ينقل الخيار الصحيح وحده بمولّد أعداد خاص؛ بتعطيله تعود الأوراق المثبتة حرفيًا،
    # فالبصمات تبقى شاهدًا على البذرة والصيغ. ما يفعله التوزيع نفسه في test_answer_positions.
    monkeypatch.setattr(services, "balance_answers", lambda questions, rng: None)
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    actual = current_digests()
    assert actual.keys() == expected.keys()
    assert [key for key in expected if actual[key] != expected[key]] == []
