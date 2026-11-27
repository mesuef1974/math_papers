"""دمج التتمة القصيرة: مقطع «تابع المثال» الذي لا يبلغ وحده حد S7 يُضمّ تحت صورة ما قبله فيُعرضان في شريحة واحدة.

الحالات الثلاث على ملف العرض نفسه (تتمة قصيرة تُدمج وتجتاز S7، تتمة طويلة تبقى شريحتها، مثال بلا تتمة لا يتغير)، وقارئ PNG
الذي يضمّ الصور بلا مكتبة: مرشّحات الأسطر وأنواع الألوان، والناتج يُقرأ هنا بـzlib مباشرةً لا بالقارئ نفسه.
"""

import hashlib
import io
import struct
import zipfile
import zlib

import pytest

from apps.assets.models import Asset
from apps.assets.storage import get_storage
from apps.assets.tests.conftest import make_png
from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import Lesson
from apps.planning import selectors, services
from apps.planning.domain.deck import DeckError, ExampleClip
from apps.planning.example_clips import (
    MERGE_GAP_SHARE,
    merge_groups,
    merge_short_continuations,
    png_size,
    short_alone,
)
from apps.planning.png_stack import rgb_rows, stack_png
from apps.planning.pptx_checks import MIN_CLIP_SHARE
from apps.planning.pptx_export import CONTENT_BOX, fit

FULL = (1600, 900)  # يملأ ارتفاع منطقة المحتوى
SHORT = (1600, 350)  # نسبته 0.22: يحدّه العرض فيقصر عن 60%
GAP = round(1600 * MERGE_GAP_SHARE)


# ---- قارئ PNG وضمّ الصور ----


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def _filtered(kind: int, row: bytes, up: bytes, bpp: int) -> bytes:
    out = bytearray()
    for i, value in enumerate(row):
        left = row[i - bpp] if i >= bpp else 0
        corner = up[i - bpp] if i >= bpp else 0
        predicted = (0, left, up[i], (left + up[i]) // 2, _paeth(left, up[i], corner))[kind]
        out.append((value - predicted) % 256)
    return bytes([kind]) + bytes(out)


def _png(width, rows, color, depth=8, kind=0, bpp=1, extra=(), interlace=0) -> bytes:
    def chunk(name: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))

    raw, up = b"", bytes(len(rows[0]))
    for row in rows:
        raw += _filtered(kind, row, up, bpp)
        up = row
    head = struct.pack(">IIBBBBB", width, len(rows), depth, color, 0, 0, interlace)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", head)
        + b"".join(chunk(name, data) for name, data in extra)
        + chunk(b"IDAT", zlib.compress(raw)[:7])  # IDAT مقسوم على قطعتين كما تكتب بعض الأدوات
        + chunk(b"IDAT", zlib.compress(raw)[7:])
        + chunk(b"IEND", b"")
    )


def _rgb_image(width: int, height: int) -> list[bytes]:
    return [
        bytes((x * 37 + y * 101 + c * 59) % 256 for x in range(width) for c in range(3))
        for y in range(height)
    ]


def _raw_rows(png: bytes) -> tuple[int, int, list[bytes]]:
    """صفوف PNG ناتج الضمّ مقروءةً بـzlib مباشرةً: RGB بثمانية بتات ومرشّح 0 في كل سطر."""
    width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", png[16:29])
    assert (depth, color, interlace) == (8, 2, 0)
    length = struct.unpack(">I", png[33:37])[0]
    assert png[37:41] == b"IDAT"
    raw = zlib.decompress(png[41 : 41 + length])
    stride = 3 * width + 1
    assert len(raw) == height * stride
    rows = [raw[y * stride : (y + 1) * stride] for y in range(height)]
    assert all(row[0] == 0 for row in rows)
    return width, height, [row[1:] for row in rows]


@pytest.mark.parametrize("kind", [0, 1, 2, 3, 4])
def test_every_row_filter_is_reversed(kind):
    rows = _rgb_image(7, 5)
    assert rgb_rows(_png(7, rows, color=2, kind=kind, bpp=3)) == (7, rows)


def test_gray_palette_and_alpha_become_rgb_over_white():
    assert rgb_rows(_png(3, [bytes([0, 128, 255])], color=0)) == (
        3,
        [bytes([0, 0, 0, 128, 128, 128, 255, 255, 255])],
    )
    # رمادي ببت واحد: 1 0 1 ثم حشو البايت
    assert rgb_rows(_png(3, [bytes([0b10100000])], color=0, depth=1)) == (
        3,
        [bytes([255, 255, 255, 0, 0, 0, 255, 255, 255])],
    )
    # لوحة بأربعة بتات: الفهرس 1 أحمر، والفهرس 2 شفاف كله فيصير أبيض
    palette = bytes([0, 0, 0, 200, 10, 20, 9, 9, 9])
    indexed = _png(
        3,
        [bytes([0x12, 0x00])],
        color=3,
        depth=4,
        extra=[(b"PLTE", palette), (b"tRNS", bytes([255, 255, 0]))],
    )
    assert rgb_rows(indexed) == (3, [bytes([200, 10, 20, 255, 255, 255, 0, 0, 0])])
    assert rgb_rows(_png(2, [bytes([40, 255, 40, 0])], color=4, bpp=2)) == (
        2,
        [bytes([40, 40, 40, 255, 255, 255])],
    )
    rgba = bytes([10, 20, 30, 255, 0, 0, 0, 51])  # الثاني أسود بشفافية 20% فوق أبيض = 204
    assert rgb_rows(_png(2, [rgba], color=6, bpp=4)) == (2, [bytes([10, 20, 30, 204, 204, 204])])


def test_stack_keeps_pixels_aligns_the_narrower_right_and_separates_with_white():
    top = _rgb_image(4, 2)
    png, width, height = stack_png(
        [_png(4, top, color=2, kind=4, bpp=3), _png(2, [bytes([7, 9])], color=0)], gap=1
    )
    assert (width, height) == (4, 4) == png_size(png)
    assert _raw_rows(png) == (
        4,
        4,
        [*top, b"\xff" * 12, b"\xff" * 6 + bytes([7, 7, 7, 9, 9, 9])],
    )
    assert (
        stack_png([_png(4, top, color=2, bpp=3)] * 2, gap=1)[0]
        == stack_png([_png(4, top, color=2, bpp=3)] * 2, 1)[0]
    )


def test_unreadable_png_is_a_loud_error_not_a_guess():
    rows = [bytes(8)]
    for bad in (
        _png(4, rows, color=0, depth=16),  # 16 بتًّا
        _png(8, rows, color=0, interlace=1),  # متشابكة
        _png(8, rows, color=3),  # لوحة بلا PLTE
        _png(9, rows, color=0),  # بيانات لا تطابق الأبعاد
        make_png(4, 4)[:-20] + b"x" * 20,  # بيانات تالفة
    ):
        with pytest.raises(DeckError):
            stack_png([bad, make_png(4, 4)], gap=1)


# ---- قرار الدمج ----


def _clip(n: int, part: int, size: tuple[int, int], shade: int = 0) -> ExampleClip:
    return ExampleClip(n=n, png=make_png(*size, shade=shade), width_px=size[0], height_px=size[1], part=part)


def test_short_alone_is_the_s7_height_rule_on_the_export_geometry():
    _, _, cx, cy = CONTENT_BOX
    for size in (FULL, SHORT, (1600, 431), (1600, 433), (4000, 300), (900, 1600)):
        assert short_alone(*size) == (fit(*size, cx, cy)[1] < MIN_CLIP_SHARE * cy), size
    assert short_alone(*SHORT) and not short_alone(*FULL)
    assert merge_groups([FULL, SHORT, FULL, SHORT, SHORT]) == [[0, 1], [2, 3, 4]]
    assert merge_groups([SHORT, FULL]) == [[0], [1]]  # الأصل القصير لا يلحق بشيء: يبقى لـS7


def test_short_continuation_is_stacked_under_the_previous_part():
    first, cont, other = _clip(1, 1, FULL, 10), _clip(1, 2, SHORT, 200), _clip(2, 1, FULL)
    merged, kept = merge_short_continuations((first, cont, other))
    assert kept is other
    assert (merged.n, merged.part, merged.width_px, merged.height_px) == (1, 1, 1600, 900 + GAP + 350)
    assert png_size(merged.png) == (merged.width_px, merged.height_px)
    assert not short_alone(merged.width_px, merged.height_px)
    _, _, rows = _raw_rows(merged.png)
    assert rows[0] == rows[899] == bytes([10]) * 4800
    assert rows[900] == rows[900 + GAP - 1] == b"\xff" * 4800
    assert rows[900 + GAP] == rows[-1] == bytes([200]) * 4800


def test_long_continuation_and_single_clip_are_returned_untouched():
    clips = (_clip(1, 1, FULL), _clip(1, 2, FULL), _clip(2, 1, FULL))
    out = merge_short_continuations(clips)
    assert len(out) == 3 and all(a is b for a, b in zip(out, clips, strict=True))
    # تتمة قصيرة بين جزأين: تُضمّ إلى الأول والطويلة بعدها تصير الجزء 2
    out = merge_short_continuations((_clip(1, 1, FULL), _clip(1, 2, SHORT), _clip(1, 3, FULL, 5)))
    assert [(c.part, c.height_px) for c in out] == [(1, 900 + GAP + 350), (2, 900)]
    assert out[1].png == make_png(*FULL, shade=5)


# ---- ملف العرض بالحالات الثلاث ----


def _asset(lesson: Lesson, n: int, part: int, size: tuple[int, int]) -> None:
    png = make_png(*size, shade=n * 7 + part)
    sha = hashlib.sha256(png).hexdigest()
    key = f"assets/{GRADE10_SLUG}/{lesson.code}/example{n}-{part}-{sha[:16]}.png"
    get_storage().put(key, png, "image/png")
    Asset.objects.create(
        course=lesson.course,
        lesson=lesson,
        kind=Asset.Kind.EXAMPLE,
        number=n,
        part=part,
        key=key,
        sha256=sha,
        size=len(png),
        width=size[0],
        height=size[1],
    )


def _deck_text_and_clips(data: bytes) -> tuple[str, list[tuple[int, int]]]:
    """نص الشرائح، وأبعاد صورة المقطع في كل شريحة مثال أو كشف بترتيبها."""
    text, sizes = "", []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = [n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
        for name in sorted(names, key=lambda n: int(n[16:-4])):
            xml = z.read(name).decode("utf-8")
            text += xml
            if 'name="مقطع' in xml:
                rels = z.read(name.replace("slides/", "slides/_rels/") + ".rels").decode("utf-8")
                media = next(part for part in rels.split('"') if "media/" in part and part.endswith(".png"))
                sizes.append(png_size(z.read("ppt/" + media.removeprefix("../"))))
    return text, sizes


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("continuation", "example_slides"),
    [(SHORT, 1), (FULL, 2), (None, 1)],
    ids=["short-merged", "long-own-slide", "no-continuation"],
)
def test_deck_file_follows_the_merge(loaded_courses, continuation, example_slides):
    first = next(p for p in selectors.lesson_preps(GRADE10_SLUG) if p.prep.examples).prep
    lesson = Lesson.objects.get(course__slug=GRADE10_SLUG, code=first.lesson)
    target = first.examples[0].n
    numbers = {
        e.n
        for p in selectors.lesson_preps(GRADE10_SLUG)
        if p.prep.lesson == first.lesson
        for e in p.prep.examples
    }
    for n in sorted(numbers):
        _asset(lesson, n, 0, FULL)
    if continuation:
        _asset(lesson, target, 1, continuation)

    prep = next(
        p.prep
        for p in selectors.lesson_preps(GRADE10_SLUG)
        if p.prep.lesson == first.lesson and target in {e.n for e in p.prep.examples}
    )
    example = next(e for e in prep.examples if e.n == target)
    assert example.continuations == example_slides
    # الوزن من مقاطع الكتاب لا من الشرائح: الضمّ لا يغيّر توزيع الأمثلة على الحصص
    assert example.weight == sum(d for d, _ in example.rows) + (1 if continuation else 0)

    key = services.build_period_deck_file(
        GRADE10_SLUG, prep.lesson, prep.k
    )  # يرفع DeckError إن فشل S7 أو غيره
    assert services.deck_state(key) == ("ready", "")
    assert key == services.prepare_deck(GRADE10_SLUG, prep.lesson, prep.k)  # المفتاح من فهرس الأصول وحده
    text, sizes = _deck_text_and_clips(get_storage().get(key))
    others = [FULL] * (len(prep.examples) - 1)  # شريحة لكل مثال آخر
    merged = (1600, 900 + GAP + 350)
    mine = {SHORT: [merged], FULL: [FULL, FULL], None: [FULL]}[continuation]
    assert sizes == [*mine, *others]
    assert (f"تابع المثال {target}" in text) == (example_slides == 2)
    assert f"مثال {target}" in text and "حل المثال" not in text
