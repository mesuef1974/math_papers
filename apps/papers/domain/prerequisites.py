"""مولّدات المتطلب السابق لكل مقرر: سؤالا تهيئة أول المقرر حين لا درس قبله (قرار المالك 2026-11-28).

خارج `generators.REGISTRY` فلا تدخل أوراقًا ولا اختبارات؛ يقرؤها `item_bank.prerequisite` وحده. مسائل أصلية بمشتتات موسومة.
"""

from __future__ import annotations

import random
from collections.abc import Callable

import sympy as sp

from apps.curriculum.courses import GRADE10_SLUG

from .generators import Problem, m, nz, tagged_wrongs, tex

LESSON = "متطلب سابق"
GRADE12 = "g12-sci-s1"


def _problem(stem: str, answer: sp.Expr, pairs: tuple, steps: tuple[str, ...], check: dict) -> Problem:
    wrong, kinds = tagged_wrongs(answer, *pairs)
    return Problem(LESSON, stem, m(answer), wrong, steps, "K", check, wrong_kinds=kinds)


def linear_equation(rng: random.Random) -> Problem:
    a, root, b = rng.randint(2, 6), sp.Integer(nz(rng, -7, 7)), nz(rng, -9, 9)
    c = a * int(root) + b
    return _problem(
        f"حُلّ المعادلة ${a}x{b:+d}={c}$.",
        root,
        (("sign", sp.Rational(c + b, a)), ("partial", sp.Integer(c - b)), ("formula", sp.Integer(c - b - a))),
        (f"${a}x={c - b}$", f"$x={tex(root)}$"),
        {"type": "linear_root", "a": a, "b": b, "c": c},
    )


def square_at_negative(rng: random.Random) -> Problem:
    k, b = rng.randint(2, 6), rng.randint(2, 7)
    value = sp.Integer(k * k - b * k)
    return _problem(
        f"أوجد قيمة $x^2+{b}x$ عندما $x=-{k}$.",
        value,
        (
            ("square", sp.Integer(-k * k - b * k)),
            ("sign", sp.Integer(k * k + b * k)),
            ("formula", sp.Integer(-2 * k - b * k)),
        ),
        (f"$(-{k})^2+{b}(-{k})$", f"$={tex(value)}$"),
        {"type": "value_at", "coefficients": [1, b, 0], "at": -k},
    )


def quadratic_value(rng: random.Random) -> Problem:
    a, b, c, k = rng.randint(2, 4), rng.randint(2, 6), nz(rng, -8, 8), rng.randint(2, 4)
    value = sp.Integer(a * k * k - b * k + c)
    return _problem(
        f"إذا كانت $f(x)={a}x^2+{b}x{c:+d}$ فأوجد $f(-{k})$.",
        value,
        (
            ("square", sp.Integer(-a * k * k - b * k + c)),
            ("sign", sp.Integer(a * k * k + b * k + c)),
            ("formula", sp.Integer((a * k) ** 2 - b * k + c)),
        ),
        (f"$f(-{k})={a}(-{k})^2+{b}(-{k}){c:+d}$", f"$={tex(value)}$"),
        {"type": "value_at", "coefficients": [a, b, c], "at": -k},
    )


def slope_two_points(rng: random.Random) -> Problem:
    x1, y1, run = rng.randint(-4, 4), rng.randint(-5, 5), rng.randint(2, 4)
    slope = sp.Integer(rng.choice([-4, -3, -2, 2, 3, 4]))
    x2, y2 = x1 + run, y1 + int(slope) * run
    return _problem(
        f"أوجد ميل المستقيم المارّ بالنقطتين $({x1},{y1})$ و$({x2},{y2})$.",
        slope,
        (("swap", 1 / slope), ("sign", -slope), ("partial", sp.Integer(y2 - y1))),
        (rf"$m=\dfrac{{{y2 - y1}}}{{{run}}}$", f"$m={tex(slope)}$"),
        {"type": "slope", "points": [[x1, y1], [x2, y2]]},
    )


PREREQUISITES: dict[str, tuple[Callable[[random.Random], Problem], ...]] = {
    GRADE10_SLUG: (linear_equation, square_at_negative),
    GRADE12: (quadratic_value, slope_two_points),
}
