"""الدرس 3.4 رسم منحنيات الدوال: ربط إشارتي f′ وf″ بشكل المنحنى، وملخص الرسم لتكعيبية، وقراءة f′ للشكل.

الدرس خارج جدول المواصفات (بلا درجات) لكنه في المنهج، فيدخل أوراق العمل والحزمة. البناء عكسي كما في
generators.py، والحقل check يحمل دالة شاهدة أو الرسم نفسه ليتحقق الاختبار عدديًا دون طريقة البناء.
"""

from __future__ import annotations

import random

import sympy as sp

from .generators import Problem, cubic_with_critical_points, m, tagged_wrongs, tex, variant, x
from .graph_problems import DERIV, derivative_graph, interval_text

SHAPES = {
    (True, True): "متزايد ومقعر لأعلى",
    (True, False): "متزايد ومقعر لأسفل",
    (False, True): "متناقص ومقعر لأعلى",
    (False, False): "متناقص ومقعر لأسفل",
}
MAX, MIN = "قيمة عظمى محلية", "قيمة صغرى محلية"


def sign_text(positive: bool) -> str:
    return ">0" if positive else "<0"


@variant("3.4", example=3)
def shape_from_signs(rng: random.Random) -> Problem:
    """إشارتا f′ وf″ على فترة تحددان شكل المنحنى (جدول الملخص في الدرس)."""
    increasing, up = rng.choice([True, False]), rng.choice([True, False])
    a = rng.randint(-4, 2)
    b = a + rng.randint(1, 3)
    # دالة شاهدة تحقق الإشارتين على (a,b): f″ ثابتة الإشارة، و|f′| يحكمه الحد الخطي الكبير
    bulge = 1 if up else -1
    slope = (1 if increasing else -1) * (2 * (b - a) + 1)
    witness = bulge * (x - a) ** 2 + slope * (x - a)
    answer = SHAPES[(increasing, up)]
    others = [text for key, text in SHAPES.items() if key != (increasing, up)]
    wrong, kinds = tagged_wrongs(answer, *(("concept", text) for text in others))
    return Problem(
        "3.4",
        f"إذا كان $f'(x){sign_text(increasing)}$ و$f''(x){sign_text(up)}$ لكل $x$ في الفترة $({a},{b})$، "
        "فما شكل منحنى الدالة $f$ على هذه الفترة؟",
        answer,
        wrong,
        (
            f"إشارة $f'$ {'موجبة فالدالة متزايدة' if increasing else 'سالبة فالدالة متناقصة'}.",
            f"إشارة $f''$ {'موجبة فالمنحنى مقعر لأعلى' if up else 'سالبة فالمنحنى مقعر لأسفل'}.",
            f"إذن المنحنى {answer}.",
        ),
        "K",
        {"type": "shape_signs", "f": witness, "low": a, "high": b, "increasing": increasing, "up": up},
        wrong_kinds=kinds,
    )


@variant("3.4", example=1)
def extremum_type_from_second_derivative(rng: random.Random) -> Problem:
    """اختبار المشتقة الثانية: f′(c)=0 وإشارة f″(c) تصنّف القيمة القصوى."""
    c = rng.randint(-4, 4)
    k = rng.choice([n for n in range(-6, 7) if n != 0])
    d = rng.randint(-5, 5)
    witness = sp.Rational(k, 2) * (x - c) ** 2 + d
    answer = MIN if k > 0 else MAX
    wrong, kinds = tagged_wrongs(
        answer,
        ("direction", MAX if k > 0 else MIN),
        ("concept", "نقطة انعطاف"),
        ("concept", "لا يمكن الاستنتاج"),
    )
    return Problem(
        "3.4",
        f"دالة $f$ قابلة للاشتقاق مرتين، و$f'({c})=0$ و$f''({c})={k}$. ماذا تستنتج عن الدالة عند $x={c}$؟",
        answer,
        wrong,
        (
            f"$f'({c})=0$ فالنقطة حرجة.",
            f"$f''({c})={k}{'>' if k > 0 else '<'}0$ فالمنحنى مقعر {'لأعلى' if k > 0 else 'لأسفل'} عندها.",
            f"إذن عند $x={c}$ {answer}.",
        ),
        "K",
        {"type": "second_derivative_test", "f": witness, "at": c, "max": k < 0},
        wrong_kinds=kinds,
    )


@variant("3.4", example=2)
def cubic_sketch_summary(rng: random.Random) -> Problem:
    """ملخص الرسم لتكعيبية: فترات التزايد والتناقص، والقيم القصوى المحلية، ونقطة الانعطاف."""
    f, p, q, sign = cubic_with_critical_points(rng)
    t = (p + q) // 2
    max_at, min_at = (p, q) if sign > 0 else (q, p)
    outside, inside = rf"$(-\infty,{p})\cup({q},\infty)$", f"$({p},{q})$"
    increasing, decreasing = (outside, inside) if sign > 0 else (inside, outside)
    answer = (
        f"متزايدة على {increasing} ومتناقصة على {decreasing}؛ "
        f"{MAX} $f({max_at})={tex(f.subs(x, max_at))}$، و{MIN} $f({min_at})={tex(f.subs(x, min_at))}$؛ "
        f"ونقطة الانعطاف $({t},{tex(f.subs(x, t))})$."
    )
    return Problem(
        "3.4",
        f"للدالة $f(x)={tex(f)}$: أوجد فترات التزايد والتناقص، والقيم القصوى المحلية، ونقطة الانعطاف، "
        "تمهيدًا لرسم منحناها.",
        answer,
        (),
        (
            f"$f'(x)={tex(sp.factor(sp.diff(f, x)))}$ وتنعدم عند $x={p}$ و$x={q}$.",
            f"$f''(x)={tex(sp.diff(f, x, 2))}$ وتنعدم عند $x={t}$ وتتغير إشارتها.",
            answer,
        ),
        "A",
        {"type": "sketch_summary", "f": f, "max_at": max_at, "min_at": min_at, "inflection": t},
        mcq_ok=False,
    )


@variant("3.4", example=3)
def shape_interval_from_derivative_graph(rng: random.Random) -> Problem:
    """من رسم f′: الفترة التي يجمع فيها المنحنى اتجاهًا وتقعرًا (قراءة الإشارة والميل معًا)."""
    graph, _, p, q, s = derivative_graph(rng)
    v = sp.Rational(p + q, 2)
    up_and_increasing = rng.choice([True, False])  # متزايد ومقعر لأعلى، وإلا متناقص ومقعر لأسفل
    right = interval_text(q, None)
    middle = f"$({p},{tex(v)})$"
    answer = right if up_and_increasing == (s > 0) else middle
    shape = SHAPES[(True, True)] if up_and_increasing else SHAPES[(False, False)]
    sign_word = "موجبة" if up_and_increasing else "سالبة"
    slope_word = "متزايدة" if up_and_increasing else "متناقصة"
    wrong, kinds = tagged_wrongs(
        answer,
        ("direction", middle if answer == right else right),
        ("concept", interval_text(None, p)),
        ("partial", f"$({tex(v)},{q})$"),
        ("partial", interval_text(p, q)),
    )
    return Problem(
        "3.4",
        f"يبيّن الشكل التمثيل البياني للمشتقة $f'$. حدد الفترة التي يكون فيها منحنى الدالة $f$ {shape}.",
        answer,
        wrong,
        (
            f"{shape.split(' و')[0]}: حيث $f'$ {sign_word}.",
            f"{'مقعر لأعلى' if up_and_increasing else 'مقعر لأسفل'}: حيث $f'$ {slope_word}.",
            f"الفترة التي تحقق الشرطين معًا: {answer}",
        ),
        "R",
        {
            "type": "graph_shape",
            "graph": graph.as_dict(),
            "low": q if answer == right else p,
            "high": None if answer == right else float(v),
            "increasing": up_and_increasing,
            "up": up_and_increasing,
        },
        graph=graph.as_dict(),
        wrong_kinds=kinds,
    )


__all__ = ["DERIV", "m"]
