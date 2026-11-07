"""وصف رسم بياني مستقل عن العرض: الخادم يحسب النقاط، والواجهة ترسمها SVG.

الوصف بيانات JSON بسيطة (أرقام فقط)، فلا يحمل نصًا يُحقن في الصفحة. الإحداثيات رياضية (y للأعلى)،
والنافذة أعداد صحيحة حتى تقع خطوط الشبكة على الأعداد كما في رسوم الكتاب.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import sympy as sp

SAMPLES = 240


@dataclass(frozen=True)
class Window:
    x_min: int
    x_max: int
    y_min: int
    y_max: int

    def __post_init__(self) -> None:
        if not (self.x_min < 0 < self.x_max and self.y_min < 0 < self.y_max):
            raise ValueError("النافذة يجب أن تحوي نقطة الأصل حتى يظهر المحوران")

    def contains(self, px: float, py: float) -> bool:
        return self.x_min <= px <= self.x_max and self.y_min <= py <= self.y_max


@dataclass
class Graph:
    window: Window
    label: str = "f"  # اسم الدالة المرسومة: f أو f′ أو f′′
    curves: list[list[tuple[float, float]]] = field(default_factory=list)
    dots: list[tuple[float, float, bool]] = field(default_factory=list)  # (x, y, مغلقة؟)
    asymptotes: list[float] = field(default_factory=list)  # خطوط رأسية متقطعة
    lines: list[list[tuple[float, float]]] = field(default_factory=list)  # مستقيمات مساعدة متقطعة (مماس)

    def add_curve(self, func: sp.Expr | Callable[[float], float], start: float, end: float) -> Graph:
        """يرسم الدالة على [start, end] ويقطع المنحنى حيث يخرج من النافذة أو لا يُعرَّف."""
        f = (
            func
            if callable(func) and not isinstance(func, sp.Expr)
            else sp.lambdify(sp.Symbol("x", real=True), func, "math")
        )
        segment: list[tuple[float, float]] = []
        for i in range(SAMPLES + 1):
            px = start + (end - start) * i / SAMPLES
            try:
                py = float(f(px))
            except (ValueError, ZeroDivisionError, OverflowError):
                py = math.nan
            margin = (self.window.y_max - self.window.y_min) * 0.02
            if math.isfinite(py) and self.window.y_min - margin <= py <= self.window.y_max + margin:
                segment.append((round(px, 4), round(py, 4)))
            elif segment:
                self._keep(segment)
                segment = []
        self._keep(segment)
        return self

    def _keep(self, segment: list[tuple[float, float]]) -> None:
        if len(segment) >= 2:
            self.curves.append(segment)

    def add_dot(self, px: float, py: float, closed: bool = True) -> Graph:
        if not self.window.contains(px, py):
            raise ValueError(f"النقطة ({px}, {py}) خارج النافذة")
        self.dots.append((float(px), float(py), closed))
        return self

    def add_asymptote(self, px: float) -> Graph:
        self.asymptotes.append(float(px))
        return self

    def add_line(self, slope: float, through: tuple[float, float]) -> Graph:
        x0, y0 = through
        w = self.window
        ends = [(w.x_min, y0 + slope * (w.x_min - x0)), (w.x_max, y0 + slope * (w.x_max - x0))]
        self.lines.append([(round(px, 4), round(py, 4)) for px, py in ends])
        return self

    def as_dict(self) -> dict[str, Any]:
        w = self.window
        return {
            "window": [w.x_min, w.x_max, w.y_min, w.y_max],
            "label": self.label,
            "curves": [[list(p) for p in c] for c in self.curves],
            "dots": [[px, py, closed] for px, py, closed in self.dots],
            "asymptotes": self.asymptotes,
            "lines": [[list(p) for p in line] for line in self.lines],
        }


def value_at(graph: dict[str, Any], px: float) -> list[float]:
    """قيم المنحنيات المرسومة عند px (للاختبارات: الجواب يُقرأ من الرسم نفسه)."""
    found = []
    for curve in graph["curves"]:
        for (x0, y0), (x1, y1) in zip(curve, curve[1:], strict=False):
            if x0 <= px <= x1 and x1 > x0:
                found.append(y0 + (y1 - y0) * (px - x0) / (x1 - x0))
                break
    return found
