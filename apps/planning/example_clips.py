"""تحميل مقصوصات أمثلة الكتاب من مجلد محلي خارج المستودع إلى مدخلات العرض.

المجلد يضعه المعلم محليًا (صفحات الدليل محتوى محميّ لا يدخل المستودع ولا Railway)، وبنيته من أداة القص: `index.json` يربط
كل درس بأمثلته (`n`, `file`, `cont` = ملفات تتمة «تابع المثال n») وبجانبه ملفات PNG. هنا قراءة وتحقق فقط: لا نص من الكتاب
ولا اختيار محتوى. الناقص لا يُخمَّن: مثال بلا ملف يُحذف، وملف مذكور غير موجود أو درس غير مفهرس خطأ.

وفيه قسمة المقطع الطويل: ما زاد ارتفاعه على `MAX_ASPECT` من عرضه يُعرض ضيّقًا لا يُقرأ، فيُقص عند فراغ أبيض بين سطوره.
مواضع القص تُحسب مرة عند النشر (`find_cuts`، تُخزَّن في `Asset.cuts`) ويقصّ العرض عندها.

وفيه دمج التتمة القصيرة: مقطع «تابع المثال» الذي لا يبلغ وحده حد S7 يُضمّ تحت صورة ما قبله فيُعرضان في شريحة واحدة.
"""

from __future__ import annotations

import json
import math
import struct
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from .domain.deck import DeckError, ExampleClip
from .png_stack import blank_rows, slice_png, stack_png
from .pptx_checks import MIN_CLIP_SHARE
from .pptx_export import CONTENT_BOX, fit

INDEX_NAME = "index.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MERGE_GAP_SHARE = 0.015  # الفاصل الأبيض بين الجزأين المضمومين من عرض الصورة
MAX_ASPECT = 1.13  # أقصى ارتفاع للشريحة من عرض مقطعها: أطول منه يشغل أقل من 40% من عرض منطقة المحتوى
MIN_GAP_SHARE = 0.008  # أضيق فراغ يُقص عنده من عرض الصورة (أوسع من الفراغ بين أجزاء الرمز الواحد)


def png_size(png: bytes) -> tuple[int, int]:
    """أبعاد PNG من ترويسة IHDR بلا مكتبة صور."""
    if not png.startswith(PNG_SIGNATURE) or png[12:16] != b"IHDR" or len(png) < 24:
        raise DeckError("ملف المقصوص ليس PNG صالحًا")
    return struct.unpack(">II", png[16:24])


def _read(root: Path, name: str, n: int, part: int) -> ExampleClip:
    path = root / name
    if path.parent != root:
        raise DeckError(f"اسم ملف مقصوص خارج المجلد: {name}")
    try:
        png = path.read_bytes()
    except OSError as exc:
        raise DeckError(f"ملف المقصوص مفقود: {name}") from exc
    width, height = png_size(png)
    return ExampleClip(n=n, png=png, width_px=width, height_px=height, part=part)


def load_example_clips(root: str | Path, lesson: str) -> tuple[ExampleClip, ...]:
    """مقصوصات الدرس مرتبة بالرقم فتتمته؛ المثال بلا ملف مقصوص يُحذف ولا يُرسم له شيء."""
    base = Path(root)
    try:
        index = json.loads((base / INDEX_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DeckError(f"فهرس المقصوصات غير مقروء في {base}") from exc
    if lesson not in index:
        raise DeckError(f"الدرس {lesson} غير مفهرس في المقصوصات")
    clips: list[ExampleClip] = []
    for entry in index[lesson]:
        if not entry.get("file"):
            continue
        clips.append(_read(base, entry["file"], entry["n"], 1))
        clips.extend(
            _read(base, name, entry["n"], part) for part, name in enumerate(entry.get("cont") or [], start=2)
        )
    return tuple(sorted(clips, key=lambda c: (c.n, c.part)))


# ---- دمج التتمة القصيرة بصورة ما قبلها ----


def short_alone(width_px: int, height_px: int) -> bool:
    """المقطع الذي يحدّه عرض منطقة المحتوى فيقصر وحده عن حد S7 (`MIN_CLIP_SHARE` من ارتفاعها)، بهندسة التصدير نفسها."""
    _, _, cx, cy = CONTENT_BOX
    return fit(width_px, height_px, cx, cy)[1] < MIN_CLIP_SHARE * cy


def _gaps(blank: Sequence[bool], least: int) -> list[int]:
    """منتصف كل فراغ داخلي ارتفاعه `least` صفًّا فأكثر (هامشا الصورة العلوي والسفلي لا يُقص عندهما)."""
    out, start = [], None
    for y, white in enumerate(blank):
        if white:
            start = y if start is None else start
        else:
            if start and y - start >= least:
                out.append((start + y) // 2)
            start = None
    return out


def find_cuts(png: bytes) -> tuple[int, ...] | None:
    """صفوف قص المقطع الطويل: () لا يحتاج قصًّا، وNone طويل بلا فراغ آمن (يبقى كما هو ويُبلَّغ).

    كل جزء بين حد القِصَر (S7) و`MAX_ASPECT`، وأقرب الفراغات إلى القسمة المتساوية."""
    width, height = png_size(png)
    tallest = math.floor(MAX_ASPECT * width)
    if height <= tallest:
        return ()
    _, _, box_cx, box_cy = CONTENT_BOX
    shortest = math.ceil(MIN_CLIP_SHARE * box_cy / box_cx * width)
    gaps = _gaps(blank_rows(png), max(2, round(MIN_GAP_SHARE * width)))
    cuts: list[int] = []
    top = 0
    while height - top > tallest:
        rest = height - top
        target = top + rest / math.ceil(rest / tallest)
        fits = [y for y in gaps if shortest <= y - top <= tallest and height - y >= shortest]
        if not fits:
            return None
        top = min(fits, key=lambda y: abs(y - target))
        cuts.append(top)
    return tuple(cuts)


def piece_sizes(width: int, height: int, cuts: Sequence[int] | None) -> list[tuple[int, int]]:
    """أبعاد أجزاء المقطع من أبعاده ومواضع قصه (من الفهرس بلا قراءة صور)."""
    edges = [0, *(cuts or ()), height]
    return [(width, b - a) for a, b in zip(edges, edges[1:], strict=False)]


def _split(clip: ExampleClip) -> list[ExampleClip]:
    if not clip.cuts:
        return [clip]
    return [
        replace(clip, png=png, width_px=width, height_px=height, cuts=())
        for png, width, height in slice_png(clip.png, clip.cuts)
    ]


def merge_groups(sizes: Sequence[tuple[int, int]]) -> list[list[int]]:
    """أجزاء المثال (أبعادها بترتيبها) مجموعاتٍ كل منها شريحة: التتمة القصيرة وحدها تلحق بما قبلها، والأصل لا يلحق بشيء.

    مصدر واحد للقرار: منه عدد شرائح المثال في التحضير (من أبعاد فهرس الأصول بلا قراءة صور) والدمج نفسه."""
    groups: list[list[int]] = []
    for i, (width, height) in enumerate(sizes):
        if groups and short_alone(width, height):
            groups[-1].append(i)
        else:
            groups.append([i])
    return groups


def merge_short_continuations(clips: Sequence[ExampleClip]) -> tuple[ExampleClip, ...]:
    """مقاطع العرض من مقاطع المصدر: الطويل يُقص عند `cuts`، ثم تتمة «تابع المثال» التي لا تبلغ حد S7 وحدها تُضمّ تحت صورة ما قبلها من المثال نفسه في
    PNG واحدة (بلا إعادة تحجيم، وبينهما فاصل أبيض) فتصير شريحة واحدة، والأجزاء تُرقَّم متصلة. ما لا دمج فيه يعود كما هو."""
    out: list[ExampleClip] = []
    for kind, n in sorted({(c.kind, c.n) for c in clips}):
        source = sorted((c for c in clips if c.kind == kind and c.n == n), key=lambda c: c.part)
        mine = [piece for clip in source for piece in _split(clip)]
        for part, group in enumerate(merge_groups([(c.width_px, c.height_px) for c in mine]), start=1):
            members = [mine[i] for i in group]
            if len(members) == 1:
                out.append(members[0] if members[0].part == part else replace(members[0], part=part))
                continue
            gap = max(1, round(max(c.width_px for c in members) * MERGE_GAP_SHARE))
            png, width, height = stack_png([c.png for c in members], gap)
            out.append(ExampleClip(n=n, png=png, width_px=width, height_px=height, part=part, kind=kind))
    return tuple(out)
