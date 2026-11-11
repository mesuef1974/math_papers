"""رسم المنحنيات على صورة PNG رمادية بلا أي اعتماد خارجي، بالأسلوب نفسه لـ GraphPlot.vue.

الوورد لا يعرض SVG بثبات، فنرسم الشبكة والمحورين والمنحنيات والنقاط المفتوحة والمغلقة بمضاعفة
3 بكسلات لكل بكسل CSS (≈ 288 نقطة في البوصة)، والأرقام بخطوط متجهية صغيرة (حروف 0-9 و − و x و y).
"""

from __future__ import annotations

import math
import struct
import zlib
from typing import Any

K = 3  # بكسل صورة لكل بكسل CSS
PAD = 22
INK = 0  # أسود
GRID = 153  # رمادي الشبكة
SOFT = 85  # رمادي أرقام المحاور

# حروف متجهية على صندوق عرضه 4 وارتفاعه 6 (الرأس للأسفل)، كل حرف خطوط متعددة النقاط.
_SIX = [
    (3.6, 0.4),
    (2.5, 0),
    (1, 0),
    (0, 1.4),
    (0, 5),
    (1, 6),
    (3, 6),
    (4, 5),
    (4, 3.6),
    (3, 2.8),
    (1, 2.8),
    (0, 3.6),
]
GLYPHS: dict[str, list[list[tuple[float, float]]]] = {
    "0": [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0)]],
    "1": [[(1, 1.2), (2.2, 0), (2.2, 6)], [(1, 6), (3.4, 6)]],
    "2": [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 2.2), (0, 6), (4, 6)]],
    "3": [
        [(0, 0.6), (1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (1.5, 3)],
        [(3, 3), (4, 4), (4, 5), (3, 6), (1, 6), (0, 5.4)],
    ],
    "4": [[(3, 6), (3, 0), (0, 4), (4, 4)]],
    "5": [[(4, 0), (0.4, 0), (0, 3), (2.6, 2.6), (4, 3.8), (4, 5), (3, 6), (1, 6), (0, 5.2)]],
    "6": [_SIX],
    "7": [[(0, 0), (4, 0), (1.6, 6)]],
    "8": [
        [(1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (1, 3), (0, 2), (0, 1), (1, 0)],
        [(1, 3), (0, 4), (0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3)],
    ],
    "9": [[(4 - x, 6 - y) for x, y in _SIX]],
    "-": [[(0.5, 3), (3.5, 3)]],
    "x": [[(0, 1.5), (4, 6)], [(4, 1.5), (0, 6)]],
    "y": [[(0, 1.5), (2, 6)], [(4, 1.5), (1, 8)]],
}
ADVANCE = 5.6


class Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.w, self.h = width, height
        self.buf = bytearray(b"\xff" * (width * height))

    def darken(self, x: int, y: int, cover: float, level: int) -> None:
        if 0 <= x < self.w and 0 <= y < self.h and cover > 0:
            index = y * self.w + x
            target = 255 - min(cover, 1.0) * (255 - level)
            if target < self.buf[index]:
                self.buf[index] = int(target)

    def lighten(self, x: int, y: int, cover: float) -> None:
        if 0 <= x < self.w and 0 <= y < self.h and cover > 0:
            index = y * self.w + x
            self.buf[index] = int(self.buf[index] + (255 - self.buf[index]) * min(cover, 1.0))

    def disc(self, cx: float, cy: float, radius: float, level: int) -> None:
        for y in range(int(cy - radius - 1), int(cy + radius + 2)):
            for x in range(int(cx - radius - 1), int(cx + radius + 2)):
                self.darken(x, y, radius + 0.5 - math.hypot(x + 0.5 - cx, y + 0.5 - cy), level)

    def ring(self, cx: float, cy: float, radius: float, width: float) -> None:
        for y in range(int(cy - radius - width - 1), int(cy + radius + width + 2)):
            for x in range(int(cx - radius - width - 1), int(cx + radius + width + 2)):
                dist = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                if dist < radius - width / 2:
                    self.lighten(x, y, 1.0)
                self.darken(x, y, width / 2 + 0.5 - abs(dist - radius), INK)

    def rect(self, x0: float, y0: float, x1: float, y1: float, level: int | None) -> None:
        """مستطيل مصمت؛ level=None يعني أبيض (هالة خلف الأرقام)."""
        for y in range(max(int(y0), 0), min(int(y1) + 1, self.h)):
            row = y * self.w
            for x in range(max(int(x0), 0), min(int(x1) + 1, self.w)):
                if level is None:
                    self.buf[row + x] = 255
                else:
                    self.buf[row + x] = min(self.buf[row + x], level)

    def line(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        width: float,
        level: int = INK,
        dash: tuple[float, float] | None = None,
    ) -> None:
        length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if length == 0:
            return
        step = 0.5
        count = int(length / step) + 1
        radius = width / 2
        for i in range(count + 1):
            d = min(i * step, length)
            if dash and (d % (dash[0] + dash[1])) > dash[0]:
                continue
            t = d / length
            self.disc(p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, radius, level)

    def polyline(
        self,
        points: list[tuple[float, float]],
        width: float,
        level: int = INK,
        dash: tuple[float, float] | None = None,
    ) -> None:
        for a, b in zip(points, points[1:], strict=False):
            self.line(a, b, width, level, dash)

    def triangle(self, a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> None:
        xs, ys = (a[0], b[0], c[0]), (a[1], b[1], c[1])

        def inside(px: float, py: float) -> bool:
            d1 = (px - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (py - b[1])
            d2 = (px - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (py - c[1])
            d3 = (px - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (py - a[1])
            return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))

        for y in range(int(min(ys)) - 1, int(max(ys)) + 2):
            for x in range(int(min(xs)) - 1, int(max(xs)) + 2):
                hits = sum(inside(x + (i + 0.5) / 3, y + (j + 0.5) / 3) for i in range(3) for j in range(3))
                self.darken(x, y, hits / 9, INK)

    def text(
        self, value: str, x: float, baseline: float, size: float, level: int, anchor: str = "start"
    ) -> None:
        """size = ارتفاع الرقم بالبكسل؛ anchor: start | middle | end (من اليسار)."""
        unit = size / 6
        width = len(value) * ADVANCE * unit - (ADVANCE - 4) * unit
        left = x - (width / 2 if anchor == "middle" else width if anchor == "end" else 0)
        top = baseline - size
        self.rect(
            left - unit, top - unit, left + width + unit, baseline + unit * (3 if "y" in value else 1), None
        )
        for index, char in enumerate(value):
            ox = left + index * ADVANCE * unit
            for stroke in GLYPHS.get(char, []):
                self.polyline(
                    [(ox + gx * unit, top + gy * unit) for gx, gy in stroke], max(unit * 0.62, 1.8), level
                )

    def png(self) -> bytes:
        raw = b"".join(b"\x00" + bytes(self.buf[y * self.w : (y + 1) * self.w]) for y in range(self.h))

        def chunk(kind: bytes, data: bytes) -> bytes:
            body = kind + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

        dpi = round(96 * K / 0.0254)
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 0, 0, 0, 0))
            + chunk(b"pHYs", struct.pack(">IIB", dpi, dpi, 1))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )


def render_graph(graph: dict[str, Any], compact: bool = False) -> tuple[bytes, float, float]:
    """يعيد (PNG، العرض، الارتفاع) بوحدة بكسل CSS، أي 96 بكسلًا للبوصة عند الحجم الطبيعي."""
    x_min, x_max, y_min, y_max = graph["window"]
    unit = 17 if compact else 26
    width, height = (x_max - x_min) * unit + PAD * 2, (y_max - y_min) * unit + PAD * 2
    canvas = Canvas(round(width * K), round(height * K))

    def sx(v: float) -> float:
        return (PAD + (v - x_min) * unit) * K

    def sy(v: float) -> float:
        return (PAD + (y_max - v) * unit) * K

    thick = round(1 * K)
    for v in range(x_min, x_max + 1):
        canvas.rect(sx(v) - thick / 2, sy(y_max), sx(v) + thick / 2, sy(y_min), GRID)
    for v in range(y_min, y_max + 1):
        canvas.rect(sx(x_min), sy(v) - thick / 2, sx(x_max), sy(v) + thick / 2, GRID)

    axis = 1.3 * K
    head = 9 * K
    x_end, y_end = sx(x_max) + 10 * K, sy(y_max) - 10 * K
    canvas.line((sx(x_min) + head * 0.6, sy(0)), (x_end - head * 0.6, sy(0)), axis)
    canvas.line((sx(0), sy(y_min) - head * 0.6), (sx(0), y_end + head * 0.6), axis)
    half = head / 2
    canvas.triangle((x_end, sy(0)), (x_end - head, sy(0) - half), (x_end - head, sy(0) + half))
    canvas.triangle((sx(x_min), sy(0)), (sx(x_min) + head, sy(0) - half), (sx(x_min) + head, sy(0) + half))
    canvas.triangle((sx(0), y_end), (sx(0) - half, y_end + head), (sx(0) + half, y_end + head))
    canvas.triangle((sx(0), sy(y_min)), (sx(0) - half, sy(y_min) - head), (sx(0) + half, sy(y_min) - head))

    dash = (6 * K, 5 * K)
    for v in graph.get("asymptotes", []):
        canvas.line((sx(v), sy(y_min)), (sx(v), sy(y_max)), 1.3 * K, INK, dash)

    size = 8.6 * K
    step = 2 if max(x_max - x_min, y_max - y_min) > 12 else 1
    for v in range(x_min + 1, x_max):
        if v != 0 and v % step == 0:
            canvas.text(str(v), sx(v), sy(0) + 15 * K, size, SOFT, "middle")
    for v in range(y_min + 1, y_max):
        if v != 0 and v % step == 0:
            canvas.text(str(v), sx(0) - 6 * K, sy(v) + 4 * K, size, SOFT, "end")
    canvas.text("x", sx(x_max) + 6 * K, sy(0) - 8 * K, size * 0.75, INK)
    canvas.text("y", sx(0) + 8 * K, sy(y_max) - 4 * K, size * 0.75, INK)

    # المنحنى في المقدمة: يُرسم بعد الشبكة والمحاور والأرقام (وهالاتها البيضاء) فلا يقطعه شيء
    for path in graph.get("lines", []):
        canvas.polyline([(sx(px), sy(py)) for px, py in path], 1.3 * K, INK, dash)
    for path in graph.get("curves", []):
        canvas.polyline([(sx(px), sy(py)) for px, py in path], 2.2 * K)

    for px, py, closed in graph.get("dots", []):
        if closed:
            canvas.disc(sx(px), sy(py), 4.2 * K + 0.9 * K, INK)
        else:
            canvas.ring(sx(px), sy(py), 4.2 * K, 1.8 * K)
    return canvas.png(), width, height
