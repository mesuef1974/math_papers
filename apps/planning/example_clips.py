"""تحميل مقصوصات أمثلة الكتاب من مجلد محلي خارج المستودع إلى مدخلات العرض.

المجلد يضعه المعلم محليًا (صفحات الدليل محتوى محميّ لا يدخل المستودع ولا Railway)، وبنيته من أداة القص: `index.json` يربط
كل درس بأمثلته (`n`, `file`, `cont` = ملفات تتمة «تابع المثال n») وبجانبه ملفات PNG. هنا قراءة وتحقق فقط: لا نص من الكتاب
ولا اختيار محتوى. الناقص لا يُخمَّن: مثال بلا ملف يُحذف، وملف مذكور غير موجود أو درس غير مفهرس خطأ.

وفيه دمج التتمة القصيرة: مقطع «تابع المثال» الذي لا يبلغ وحده حد S7 يُضمّ تحت صورة ما قبله فيُعرضان في شريحة واحدة.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from .domain.deck import DeckError, ExampleClip
from .png_stack import stack_png
from .pptx_checks import MIN_CLIP_SHARE
from .pptx_export import CONTENT_BOX, fit

INDEX_NAME = "index.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MERGE_GAP_SHARE = 0.015  # الفاصل الأبيض بين الجزأين المضمومين من عرض الصورة


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
    """مقاطع العرض من مقاطع المصدر: تتمة «تابع المثال» التي لا تبلغ حد S7 وحدها تُضمّ تحت صورة ما قبلها من المثال نفسه في
    PNG واحدة (بلا إعادة تحجيم، وبينهما فاصل أبيض) فتصير شريحة واحدة، والأجزاء تُرقَّم متصلة. ما لا دمج فيه يعود كما هو."""
    out: list[ExampleClip] = []
    for kind, n in sorted({(c.kind, c.n) for c in clips}):
        mine = sorted((c for c in clips if c.kind == kind and c.n == n), key=lambda c: c.part)
        for part, group in enumerate(merge_groups([(c.width_px, c.height_px) for c in mine]), start=1):
            members = [mine[i] for i in group]
            if len(members) == 1:
                out.append(members[0] if members[0].part == part else replace(members[0], part=part))
                continue
            gap = max(1, round(max(c.width_px for c in members) * MERGE_GAP_SHARE))
            png, width, height = stack_png([c.png for c in members], gap)
            out.append(ExampleClip(n=n, png=png, width_px=width, height_px=height, part=part, kind=kind))
    return tuple(out)
