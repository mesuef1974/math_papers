"""تجهيزات عروض الحصص المشتركة بين اختبارات النموذج (`test_period_deck.py`) والملف (`test_pptx_files.py`).

حصص العاشر الـ48 بمقاطع PNG صالحة (`make_png` من اختبارات الأصول) لكل مثال وتتماته. التجهيزات مسجَّلة بـ
`pytest_plugins` في conftest الجذري، والدوال تُستورد.
"""

import pytest

from apps.assets.tests.conftest import make_png
from apps.curriculum.courses import GRADE10_SLUG
from apps.planning.domain.deck import ExampleClip, build_period_deck
from apps.planning.selectors import lesson_preps

CLIP_W, CLIP_H = 1600, 900
CLIP_PNG = make_png(CLIP_W, CLIP_H)


def fake_clips(prep, png: bytes = CLIP_PNG) -> tuple[ExampleClip, ...]:
    """مقطع لكل مثال وتتماته بعدد مقاطعه المعروف (وواحد إن لم تُنشر الأصول)."""
    return tuple(
        ExampleClip(n=e.n, png=png, width_px=CLIP_W, height_px=CLIP_H, part=part)
        for e in prep.examples
        for part in range(1, (e.continuations or 1) + 1)
    )


def middle_of(built):
    """حصة أمثلة فيها تدريب صفي وتمايز وبطاقة خروج ورقم تمرين متتالٍ (للمدى)."""
    return next(b for b in built if b[0].examples and b[0].classwork and b[0].exit_ticket and b[0].basic)


@pytest.fixture
def preps(loaded_courses):
    return lesson_preps(GRADE10_SLUG)


@pytest.fixture
def built(preps):
    """(التحضير، معاييره، المقاطع، العرض) لكل حصة."""
    out = []
    for row in preps:
        clips = fake_clips(row.prep)
        out.append((row.prep, row.checks, clips, build_period_deck(row.prep, clips)))
    return out
