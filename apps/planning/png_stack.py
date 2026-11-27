"""ضمّ صور PNG عموديًا في صورة واحدة وقصّها صفوفًا بلا مكتبة صور (Pillow ليست من تبعيات التشغيل).

كل صورة تُفكّ إلى صفوف RGB بثمانية بتات (الشفاف فوق أبيض)، وتُرصّ الصفوف بعرض أعرضها بلا إعادة تحجيم: الأضيق يُحاذى يمينًا
(بداية السطر في كتاب عربي) وما بقي أبيض، وبين الصورتين فاصل أبيض. يُقرأ ما تكتبه أدوات القص: رمادي وملوّن ولوحة ألوان،
بثمانية بتات أو أقل، غير متشابك؛ وغيره خطأ صريح لا تخمين.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Sequence
from functools import cache
from itertools import accumulate

from .domain.deck import DeckError

SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}  # نوع اللون ← عدد قنواته
GRAY, PALETTE, GRAY_ALPHA, RGBA = 0, 3, 4, 6


def _chunks(png: bytes):
    if not png.startswith(SIGNATURE):
        raise DeckError("صورة المقطع ليست PNG")
    pos = len(SIGNATURE)
    while pos + 8 <= len(png):
        length, kind = struct.unpack(">I4s", png[pos : pos + 8])
        yield kind, png[pos + 8 : pos + 8 + length]
        pos += 12 + length


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _add(line: bytearray, prev: bytes) -> bytearray:
    """جمع بايت ببايت (mod 256) على السطر كله دفعة واحدة: السبعة الدنيا تُجمع بلا حمل بين البايتات ثم يُردّ البت الأعلى."""
    n = len(line)
    low = int.from_bytes(b"\x7f" * n, "big")
    x, y = int.from_bytes(line, "big"), int.from_bytes(prev, "big")
    total = ((x & low) + (y & low)) ^ ((x ^ y) & (low << 1) & ~low)
    return bytearray(total.to_bytes(n, "big"))


def _unfilter(kind: int, line: bytearray, prev: bytes, bpp: int) -> bytearray:
    """يعكس مرشّح السطر (PNG، المرشّحات 0 إلى 4)؛ `prev` السطر السابق بعد فكّه و`bpp` بايتات البكسل."""
    if kind == 0:
        return line
    if kind == 1:
        for c in range(bpp):
            line[c::bpp] = bytes(v & 255 for v in accumulate(line[c::bpp]))
        return line
    if kind == 2:
        return _add(line, prev)
    if kind == 3:
        for i in range(len(line)):
            left = line[i - bpp] if i >= bpp else 0
            line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        return line
    if kind == 4:
        for i in range(len(line)):
            a, c = (line[i - bpp], prev[i - bpp]) if i >= bpp else (0, 0)
            b = prev[i]
            pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
            line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        return line
    raise DeckError("مرشّح سطر غير معروف في صورة المقطع")


@cache
def _unpack_table(depth: int) -> tuple[bytes, ...]:
    """لكل بايت عيّناته حين العيّنة أقل من ثمانية بتات (1 و2 و4)."""
    mask = (1 << depth) - 1
    return tuple(
        bytes((byte >> shift) & mask for shift in range(8 - depth, -1, -depth)) for byte in range(256)
    )


def _samples(line: bytes, width: int, depth: int) -> bytes:
    if depth == 8:
        return bytes(line)
    table = _unpack_table(depth)
    return b"".join(table[b] for b in line)[:width]


def _over_white(channel: bytes, alpha: bytes) -> bytes:
    if alpha.count(255) == len(alpha):
        return channel
    return bytes((c * a + 255 * (255 - a) + 127) // 255 for c, a in zip(channel, alpha, strict=True))


def _palette_tables(palette: bytes, alpha: bytes) -> tuple[bytes, bytes, bytes]:
    tables = []
    for c in range(3):
        table = bytearray(256)
        for i in range(len(palette) // 3):
            a = alpha[i] if i < len(alpha) else 255
            table[i] = (palette[3 * i + c] * a + 255 * (255 - a) + 127) // 255
        tables.append(bytes(table))
    return tables[0], tables[1], tables[2]


def rgb_rows(png: bytes) -> tuple[int, list[bytes]]:
    """عرض الصورة وصفوفها RGB بثمانية بتات، والشفاف فوق أبيض."""
    header, palette, alpha, data = b"", b"", b"", []
    for kind, body in _chunks(png):
        if kind == b"IHDR":
            header = body
        elif kind == b"PLTE":
            palette = body
        elif kind == b"tRNS":
            alpha = body
        elif kind == b"IDAT":
            data.append(body)
    if len(header) != 13:
        raise DeckError("صورة المقطع بلا ترويسة PNG")
    width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", header)
    channels = CHANNELS.get(color)
    packed = depth in (1, 2, 4) and color in (GRAY, PALETTE)
    if channels is None or interlace or not (depth == 8 or packed) or (color == PALETTE and not palette):
        raise DeckError(
            f"صيغة PNG لا تُضمّ: نوع اللون {color} بعمق {depth}" + ("، متشابكة" if interlace else "")
        )
    stride = (width * channels * depth + 7) // 8
    bpp = max(1, channels * depth // 8)
    try:
        raw = zlib.decompress(b"".join(data))
    except zlib.error as exc:
        raise DeckError("بيانات صورة المقطع تالفة") from exc
    if len(raw) != height * (stride + 1):
        raise DeckError("بيانات صورة المقطع لا تطابق أبعادها")
    tables = _palette_tables(palette, alpha) if color == PALETTE else None
    scale = bytes(i * 255 // ((1 << depth) - 1) for i in range(1 << depth)).ljust(256, b"\x00")
    rows: list[bytes] = []
    prev = bytes(stride)
    for y in range(height):
        start = y * (stride + 1)
        line = _unfilter(raw[start], bytearray(raw[start + 1 : start + 1 + stride]), prev, bpp)
        prev = line
        if color == 2:
            rows.append(bytes(line))
            continue
        out = bytearray(3 * width)
        if color == GRAY:
            out[0::3] = out[1::3] = out[2::3] = _samples(line, width, depth).translate(scale)
        elif color == PALETTE:
            index = _samples(line, width, depth)
            for c in range(3):
                out[c::3] = index.translate(tables[c])
        elif color == GRAY_ALPHA:
            out[0::3] = out[1::3] = out[2::3] = _over_white(bytes(line[0::2]), bytes(line[1::2]))
        else:
            opacity = bytes(line[3::4])
            for c in range(3):
                out[c::3] = _over_white(bytes(line[c::4]), opacity)
        rows.append(bytes(out))
    return width, rows


def stack_png(parts: Sequence[bytes], gap: int) -> tuple[bytes, int, int]:
    """الصور بترتيبها من أعلى إلى أسفل في PNG واحدة (RGB) وبينها `gap` صفًّا أبيض: (الصورة، عرضها، ارتفاعها)."""
    decoded = [rgb_rows(part) for part in parts]
    width = max(w for w, _ in decoded)
    blank = b"\x00" + b"\xff" * (3 * width)
    lines: list[bytes] = []
    for i, (w, rows) in enumerate(decoded):
        if i:
            lines.extend([blank] * gap)
        pad = b"\x00" + b"\xff" * (3 * (width - w))  # مرشّح السطر 0 ثم بياض يسار الأضيق
        lines.extend(pad + row for row in rows)
    return _encode(width, lines), width, len(lines)


def _encode(width: int, lines: Sequence[bytes]) -> bytes:
    """PNG ملوّنة من أسطر كل منها بايت المرشّح 0 ثم صف RGB."""
    return (
        SIGNATURE
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, len(lines), 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(b"".join(lines)))
        + _chunk(b"IEND", b"")
    )


def blank_rows(png: bytes, light: int = 235, ink: float = 0.005) -> list[bool]:
    """لكل صف: أهو فراغ أبيض؟ ما دون `light` حبر، ويُغتفر منه `ink` من الصف (خط إطار جانبي أو شائبة مسح)."""
    width, rows = rgb_rows(png)
    pale, limit = bytes(range(light, 256)), int(3 * width * ink)
    return [len(row.translate(None, pale)) <= limit for row in rows]


def slice_png(png: bytes, cuts: Sequence[int]) -> list[tuple[bytes, int, int]]:
    """الصورة أجزاءً عند صفوف `cuts` المتزايدة (أول صف في كل جزء تالٍ): (الصورة، عرضها، ارتفاعها) لكل جزء."""
    width, rows = rgb_rows(png)
    edges = [0, *cuts, len(rows)]
    if any(a >= b for a, b in zip(edges, edges[1:], strict=False)):
        raise DeckError("مواضع قص المقطع خارج صورته أو غير متزايدة")
    return [
        (_encode(width, [b"\x00" + row for row in rows[a:b]]), width, b - a)
        for a, b in zip(edges, edges[1:], strict=False)
    ]
