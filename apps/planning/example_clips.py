"""تحميل مقصوصات أمثلة الكتاب من مجلد محلي خارج المستودع إلى مدخلات العرض.

المجلد يضعه المعلم محليًا (صفحات الدليل محتوى محميّ لا يدخل المستودع ولا Railway)، وبنيته من أداة القص: `index.json` يربط
كل درس بأمثلته (`n`, `file`, `cont` = ملفات تتمة «تابع المثال n») وبجانبه ملفات PNG. هنا قراءة وتحقق فقط: لا نص من الكتاب
ولا اختيار محتوى. الناقص لا يُخمَّن: مثال بلا ملف يُحذف، وملف مذكور غير موجود أو درس غير مفهرس خطأ.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from .domain.deck import DeckError, ExampleClip

INDEX_NAME = "index.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


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
