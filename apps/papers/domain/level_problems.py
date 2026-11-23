"""صيغ تكمل المستويات: لكل درس سؤال سهل (K) وسؤال مهارات عليا (R)، مع أنواع تتكرر في الاختبار.

البناء عكسي كما في generators.py: الجواب يُختار أولًا ثم تُبنى المسألة حوله بأعداد نظيفة.
"""

from __future__ import annotations

import random

import sympy as sp

from .generators import (
    Problem,
    cases,
    cubic_with_critical_points,
    frac,
    lim,
    m,
    nz,
    tagged_wrongs,
    tex,
    variant,
    x,
    y,
)

YES, NO = "نعم", "لا"
CONTINUOUS, NOT_CONTINUOUS = "متصلة", "غير متصلة"


def joined(points: list) -> str:
    return " و".join(f"$x={tex(p)}$" for p in points)


# الوحدة الأولى
@variant("1.1", example=2)
def limit_exists_parameter(rng: random.Random) -> Problem:
    """قيمة ثابت تجعل النهاية موجودة: يجب أن تتساوى النهايتان من الجهتين."""
    c = nz(rng, -2, 3)
    a = nz(rng, -4, 4)
    k = rng.randint(-5, 5)
    target = c**2 + k  # النهاية من اليمين
    left = a * x + (target - a * c)  # المعامل a مجهول في السؤال، والحد الثابت معطى
    constant = target - a * c
    a_sym = sp.Symbol("a")
    shown_left = a_sym * x + constant
    function = cases((shown_left, f"x<{c}"), (x**2 + k, rf"x \ge {c}"))
    wrong, kinds = tagged_wrongs(
        sp.Integer(a),
        ("sign", sp.Integer(-a)),
        ("concept", sp.Integer(target)),
        ("nearby", sp.Integer(a + 1)),
    )
    return Problem(
        "1.1",
        f"إذا كانت ${function}$ فأوجد قيمة الثابت $a$ التي تجعل ${lim(c, 'f(x)')}$ موجودة.",
        m(a),
        wrong,
        (
            f"${lim(f'{c}^+', 'f(x)')}={tex(c)}^2{k:+d}={target}$",
            f"${lim(f'{c}^-', 'f(x)')}={c}a{constant:+d}$",
            f"تتساويان: ${c}a{constant:+d}={target}$ فإن $a={a}$",
        ),
        "R",
        {"type": "one_sided", "left": left, "right": x**2 + k, "at": c, "value": sp.Integer(target)},
        wrong_kinds=kinds,
    )


@variant("1.2", example=1)
def limit_properties(rng: random.Random) -> Problem:
    c = rng.randint(-3, 4)
    lf, lg = nz(rng, -6, 6), nz(rng, -5, 5)
    p, q = nz(rng, -3, 4), nz(rng, -3, 3)
    # دالتان حقيقيتان لهما النهايتان المعطاتان، فيتحقق الاختبار من النهاية فعلًا
    f_real, g_real = lf + 2 * (x - c), lg - (x - c)
    form = rng.choice(["linear", "product", "square"])
    if form == "linear":
        expr, real = rf"\left[{p}f(x){q:+d}g(x)\right]", p * f_real + q * g_real
        value = p * lf + q * lg
        wrong_pool = [("sign", p * lf - q * lg), ("formula", lf + lg), ("formula", p + q)]
    elif form == "product":
        expr, real = r"\left[f(x)\cdot g(x)\right]", f_real * g_real
        value = lf * lg
        wrong_pool = [("formula", lf + lg), ("formula", lf - lg), ("nearby", lf * lg + 1)]
    else:
        expr, real = rf"\left[f(x)\right]^2{p:+d}g(x)", f_real**2 + p * g_real
        value = lf**2 + p * lg
        wrong_pool = [("square", 2 * lf + p * lg), ("sign", lf**2 - p * lg), ("square", lf + p * lg)]
    wrong, kinds = tagged_wrongs(sp.Integer(value), *((kind, sp.Integer(v)) for kind, v in wrong_pool))
    return Problem(
        "1.2",
        f"إذا علمت أن ${lim(c, 'f(x)')}={lf}$ و${lim(c, 'g(x)')}={lg}$ فأوجد ${lim(c, expr)}$.",
        m(value),
        wrong,
        ("نطبق خصائص النهايات: نهاية المجموع والضرب والقوة.", f"الناتج ${value}$"),
        "K",
        {"type": "limit", "expr": real, "at": c, "value": sp.Integer(value)},
        wrong_kinds=kinds,
    )


@variant("1.2", example=3)
def limit_parameter_factoring(rng: random.Random) -> Problem:
    """قيمة k تجعل النهاية موجودة (البسط يجب أن ينعدم)، ثم قيمة النهاية."""
    c = nz(rng, -3, 3)
    r = rng.choice([v for v in range(-4, 5) if v != c])
    k = -(c + r)
    numerator = x**2 + k * x + c * r
    value = c - r
    k_sym = sp.Symbol("k")
    shown = frac(x**2 + k_sym * x + c * r, x - c)
    answer = f"$k={k}$، والنهاية ${value}$"
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", f"$k={-k}$، والنهاية ${value}$"),
        ("formula", f"$k={k}$، والنهاية ${c + r}$"),
        ("sign", f"$k={k}$، والنهاية ${-value}$"),
        ("nearby", f"$k={k + 1}$، والنهاية ${value}$"),
    )
    return Problem(
        "1.2",
        f"أوجد قيمة الثابت $k$ التي تجعل ${lim(c, shown)}$ موجودة، ثم أوجد قيمة النهاية.",
        answer,
        wrong,
        (
            f"المقام ينعدم عند $x={c}$، فلكي توجد النهاية يجب أن ينعدم البسط: ${c * c}{c:+d}k{c * r:+d}=0$ فإن $k={k}$.",
            f"$x^2{k:+d}x{c * r:+d}=(x{-c:+d})(x{-r:+d})$",
            f"${lim(c, f'(x{-r:+d})')}={value}$",
        ),
        "R",
        {"type": "limit", "expr": numerator / (x - c), "at": c, "value": sp.Integer(value)},
        wrong_kinds=kinds,
    )


@variant("1.3", example=2)
def limit_sine_simple(rng: random.Random) -> Problem:
    a, b = nz(rng, 2, 9), nz(rng, 1, 5)
    value = sp.Rational(a, b)
    wrong, kinds = tagged_wrongs(
        value,
        ("swap", sp.Rational(b, a)),
        ("formula", sp.Integer(a)),
        ("concept", sp.Integer(0)),
        ("concept", sp.Integer(1)),
    )
    return Problem(
        "1.3",
        f"أوجد ${lim(0, frac(sp.sin(a * x), b * x))}$.",
        m(value),
        wrong,
        (
            rf"$\lim\limits_{{x\to0}}\dfrac{{\sin {a}x}}{{{a}x}}=1$",
            f"إذن النهاية $\\dfrac{{{a}}}{{{b}}}={tex(value)}$",
        ),
        "K",
        {"type": "limit", "expr": sp.sin(a * x) / (b * x), "at": 0, "value": value},
        wrong_kinds=kinds,
    )


@variant("1.3", example=4)
def limit_sine_tangent_product(rng: random.Random) -> Problem:
    """نهاية حاصل ضرب نسبتين مثلثيتين: تتطلب تفكيك الكسر إلى نهايتين معروفتين."""
    a, b = rng.randint(2, 7), rng.randint(2, 7)
    c = rng.choice([1, 2, 3, 4, 6])
    value = sp.Rational(a * b, c)
    body = frac(sp.sin(a * x) * sp.tan(b * x), c * x**2)
    wrong, kinds = tagged_wrongs(
        value,
        ("formula", sp.Rational(a + b, c)),
        ("formula", sp.Integer(a * b)),
        ("swap", sp.Rational(c, a * b)),
        ("concept", sp.Integer(0)),
    )
    return Problem(
        "1.3",
        f"أوجد ${lim(0, body)}$.",
        m(value),
        wrong,
        (
            rf"$=\dfrac{{1}}{{{c}}}\cdot\lim\limits_{{x\to0}}\dfrac{{\sin {a}x}}{{x}}\cdot\lim\limits_{{x\to0}}\dfrac{{\tan {b}x}}{{x}}$",
            rf"$=\dfrac{{1}}{{{c}}}\cdot {a}\cdot {b}={tex(value)}$",
        ),
        "R",
        {"type": "limit", "expr": sp.sin(a * x) * sp.tan(b * x) / (c * x**2), "at": 0, "value": value},
        wrong_kinds=kinds,
    )


@variant("1.4", example=5)
def continuity_yes_no(rng: random.Random) -> Problem:
    c = rng.randint(-2, 3)
    a, b = nz(rng, -3, 3), rng.randint(-4, 4)
    left = a * x + b
    meeting = left.subs(x, c)
    joined_ok = rng.random() < 0.5
    right_const = meeting - c**2 if joined_ok else meeting - c**2 + nz(rng, -3, 3)
    right = x**2 + right_const
    function = cases((left, f"x<{c}"), (right, rf"x \ge {c}"))
    answer = CONTINUOUS if joined_ok else NOT_CONTINUOUS
    wrong, kinds = tagged_wrongs(
        answer,
        ("concept", CONTINUOUS),
        ("concept", NOT_CONTINUOUS),
        ("concept", "غير معرفة عند هذه النقطة"),
        ("concept", "النهاية غير موجودة لكنها متصلة"),
    )
    return Problem(
        "1.4",
        f"هل الدالة ${function}$ متصلة عند $x={c}$؟",
        answer,
        wrong,
        (
            f"${lim(f'{c}^-', 'f(x)')}={meeting}$",
            f"${lim(f'{c}^+', 'f(x)')}=f({c})={right.subs(x, c)}$",
            f"إذن الدالة {answer} عند $x={c}$.",
        ),
        "K",
        {"type": "continuity_bool", "left": left, "right": right, "at": c, "continuous": joined_ok},
        wrong_kinds=kinds,
    )


@variant("1.4", example=2)
def continuity_two_constants(rng: random.Random) -> Problem:
    p = rng.choice([-2, -1, 1])
    q = p + rng.choice([2, 3])
    a, b = nz(rng, -3, 4), nz(rng, -3, 4)
    c1, c2 = p**2 - a * p, q**2 - b * q
    a_sym, b_sym = sp.symbols("a b")
    function = cases(
        (a_sym * x + c1, f"x<{p}"),
        (x**2, rf"{p} \le x \le {q}"),
        (b_sym * x + c2, f"x>{q}"),
    )
    answer = f"$a={a}$، $b={b}$"
    wrong, kinds = tagged_wrongs(
        answer,
        ("swap", f"$a={b}$، $b={a}$"),
        ("sign", f"$a={-a}$، $b={b}$"),
        ("sign", f"$a={a}$، $b={-b}$"),
        ("nearby", f"$a={a + 1}$، $b={b}$"),
    )
    return Problem(
        "1.4",
        f"أوجد قيمتي الثابتين $a$ و$b$ اللتين تجعلان الدالة ${function}$ متصلة على $\\mathbb{{R}}$.",
        answer,
        wrong,
        (
            f"عند $x={p}$: ${p}a{c1:+d}={p**2}$ فإن $a={a}$.",
            f"عند $x={q}$: ${q}b{c2:+d}={q**2}$ فإن $b={b}$.",
        ),
        "R",
        {"type": "continuity2", "left": a * x + c1, "mid": x**2, "right": b * x + c2, "p": p, "q": q},
        wrong_kinds=kinds,
    )


# الوحدة الثانية
@variant("2.1", example=2)
def average_rate_from_table(rng: random.Random) -> Problem:
    a0, a1, a2 = rng.randint(-3, 3), rng.randint(-4, 4), nz(rng, -2, 2)
    f = a2 * x**2 + a1 * x + a0
    xs = sorted(rng.sample(range(-2, 5), 4))
    i, j = sorted(rng.sample(range(4), 2))
    lo, hi = xs[i], xs[j]
    value = sp.Rational(f.subs(x, hi) - f.subs(x, lo), hi - lo)
    header = " & ".join(str(v) for v in xs)
    row = " & ".join(str(f.subs(x, v)) for v in xs)
    table = rf"\begin{{array}}{{c|cccc}} x & {header} \\ \hline f(x) & {row} \end{{array}}"
    wrong, kinds = tagged_wrongs(
        value,
        ("formula", f.subs(x, hi) - f.subs(x, lo)),
        ("sign", -value),
        ("concept", sp.Rational(hi - lo, 1)),
        ("nearby", value + 1),
    )
    return Problem(
        "2.1",
        f"يبيّن الجدول قيمًا للدالة $f$: ${table}$ أوجد معدل التغير المتوسط للدالة على الفترة $[{lo},{hi}]$.",
        m(value),
        wrong,
        (
            rf"$\dfrac{{f({hi})-f({lo})}}{{{hi}-({lo})}}=\dfrac{{{f.subs(x, hi)}-({f.subs(x, lo)})}}{{{hi - lo}}}={tex(value)}$",
        ),
        "K",
        {"type": "average", "f": f, "a": lo, "b": hi, "value": value},
        wrong_kinds=kinds,
    )


@variant("2.1", example=4)
def instantaneous_equals_average(rng: random.Random) -> Problem:
    lo = rng.randint(-3, 1)
    hi = lo + 2 * rng.randint(1, 3)
    a2, a1 = nz(rng, -2, 3), rng.randint(-4, 4)
    f = a2 * x**2 + a1 * x + rng.randint(-3, 3)
    point = sp.Rational(lo + hi, 2)
    wrong, kinds = tagged_wrongs(
        point,
        ("nearby", point + 1),
        ("concept", sp.Integer(lo)),
        ("concept", sp.Integer(hi)),
        ("nearby", point - 1),
    )
    return Problem(
        "2.1",
        f"للدالة $f(x)={tex(f)}$، أوجد قيمة $x$ في الفترة $({lo},{hi})$ التي يكون عندها معدل التغير اللحظي مساويًا لمعدل التغير المتوسط على $[{lo},{hi}]$.",
        m(point),
        wrong,
        (
            rf"المتوسط $\dfrac{{f({hi})-f({lo})}}{{{hi}-({lo})}}={tex(sp.Rational(f.subs(x, hi) - f.subs(x, lo), hi - lo))}$",
            f"$f'(x)={tex(sp.diff(f, x))}$، نساويه بالمتوسط فنجد $x={tex(point)}$",
        ),
        "R",
        {"type": "avg_instant", "f": f, "a": lo, "b": hi, "point": point},
        wrong_kinds=kinds,
    )


@variant("2.2", example=1)
def derivative_definition_at_point(rng: random.Random) -> Problem:
    a2, a1, a0 = nz(rng, -3, 3), rng.randint(-5, 5), rng.randint(-4, 4)
    a = rng.randint(-2, 3)
    f = a2 * x**2 + a1 * x + a0
    value = sp.diff(f, x).subs(x, a)
    h = sp.Symbol("h")
    quotient = sp.expand((f.subs(x, a + h) - f.subs(x, a)) / h)
    wrong, kinds = tagged_wrongs(
        value,
        ("concept", f.subs(x, a)),
        ("formula", value + a2),
        ("sign", -value),
    )
    return Problem(
        "2.2",
        f"استعمل تعريف المشتقة لإيجاد $f'({a})$ للدالة $f(x)={tex(f)}$.",
        m(value),
        wrong,
        (
            rf"$f'({a})=\lim\limits_{{h\to0}}\dfrac{{f({a}+h)-f({a})}}{{h}}$",
            rf"$=\lim\limits_{{h\to0}}\left({tex(quotient)}\right)={tex(value)}$",
        ),
        "A",
        {"type": "limit", "expr": (f.subs(x, a + x) - f.subs(x, a)) / x, "at": 0, "value": value},
        wrong_kinds=kinds,
    )


@variant("2.2", example=5)
def differentiability_piecewise(rng: random.Random) -> Problem:
    c = rng.randint(-2, 2)
    p = rng.randint(-3, 3)
    differentiable = rng.random() < 0.5
    slope = 2 * c if differentiable else 2 * c + nz(rng, -2, 2)
    left = x**2 + p
    right = slope * x + (c**2 + p - slope * c)  # متصلة بالبناء
    function = cases((left, rf"x \le {c}"), (right, f"x>{c}"))
    answer = YES if differentiable else NO
    verdict = (
        "متساويتان، فالدالة قابلة للاشتقاق." if differentiable else "مختلفتان، فالدالة غير قابلة للاشتقاق."
    )
    wrong, kinds = tagged_wrongs(
        answer,
        ("concept", YES),
        ("concept", NO),
        ("concept", "لا يمكن الحكم"),
        ("partial", "قابلة للاشتقاق من اليسار فقط"),
    )
    return Problem(
        "2.2",
        f"الدالة ${function}$ متصلة عند $x={c}$. هل هي قابلة للاشتقاق عند $x={c}$؟",
        answer,
        wrong,
        (
            f"المشتقة من اليسار $2x$ عند $x={c}$ تساوي ${2 * c}$.",
            f"المشتقة من اليمين تساوي ${slope}$.",
            f"المشتقتان {verdict}",
        ),
        "R",
        {"type": "differentiable", "left": left, "right": right, "at": c, "answer": differentiable},
        wrong_kinds=kinds,
    )


@variant("2.3", example=4)
def derivative_polynomial_simple(rng: random.Random) -> Problem:
    n1, n2 = rng.sample([2, 3, 4, 5], 2)
    a, b, c = nz(rng, -6, 6), nz(rng, -5, 5), rng.randint(-9, 9)
    f = a * x**n1 + b * x**n2 + c
    d = sp.diff(f, x)
    wrong, kinds = tagged_wrongs(
        d,
        ("partial", d + c),
        ("partial", sp.expand(a * x ** (n1 - 1) + b * x ** (n2 - 1))),
        ("formula", sp.expand(a * n1 * x**n1 + b * n2 * x**n2)),
    )
    return Problem(
        "2.3",
        f"أوجد $f'(x)$ للدالة $f(x)={tex(f)}$.",
        m(d),
        wrong,
        ("مشتقة $x^n$ هي $nx^{n-1}$، ومشتقة الثابت صفر.", f"$f'(x)={tex(d)}$"),
        "K",
        {"type": "function", "f": f, "d": d, "order": 1},
        wrong_kinds=kinds,
    )


@variant("2.3", example=5)
def tangent_line_equation(rng: random.Random) -> Problem:
    a3, a2, a1 = rng.choice([0, 0, 1, -1]), nz(rng, -2, 3), rng.randint(-4, 4)
    f = a3 * x**3 + a2 * x**2 + a1 * x + rng.randint(-3, 3)
    a = rng.randint(-2, 2)
    slope = sp.diff(f, x).subs(x, a)
    point = f.subs(x, a)
    intercept = point - slope * a
    line = sp.expand(slope * x + intercept)
    wrong, kinds = tagged_wrongs(
        f"$y={tex(line)}$",
        ("formula", f"$y={tex(sp.expand(slope * x + point))}$"),
        ("swap", f"$y={tex(sp.expand(point * x + intercept))}$"),
        ("sign", f"$y={tex(sp.expand(-slope * x + point + slope * a))}$"),
        ("nearby", f"$y={tex(sp.expand(slope * x + intercept + 1))}$"),
        ("nearby", f"$y={tex(sp.expand((slope + 1) * x + intercept))}$"),
        ("sign", f"$y={tex(sp.expand(slope * x - intercept))}$"),
        ("formula", f"$y={tex(sp.expand(x + intercept))}$"),
        ("formula", f"$y={tex(sp.expand(-x + intercept))}$"),
        ("formula", f"$y={tex(intercept - 1)}$"),
    )
    return Problem(
        "2.3",
        f"أوجد معادلة المماس لمنحنى الدالة $f(x)={tex(f)}$ عند $x={a}$.",
        f"$y={tex(line)}$",
        wrong,
        (
            f"النقطة $({a},{point})$، والميل $f'({a})={slope}$.",
            f"$y-({point})={slope}(x-({a}))$ أي $y={tex(line)}$",
        ),
        "A",
        {"type": "tangent", "f": f, "at": a, "slope": slope, "intercept": intercept},
        wrong_kinds=kinds,
    )


@variant("2.3", example=5)
def horizontal_tangent_points(rng: random.Random) -> Problem:
    f, p, q, _ = cubic_with_critical_points(rng)
    answer = joined([p, q])
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", joined([-p, -q])),
        ("partial", joined([p])),
        ("partial", joined([q])),
        ("formula", joined([p + q])),
    )
    return Problem(
        "2.3",
        f"أوجد قيم $x$ التي يكون عندها المماس لمنحنى $f(x)={tex(f)}$ أفقيًا.",
        answer,
        wrong,
        (
            "المماس أفقي حيث ميله صفر: $f'(x)=0$.",
            f"$f'(x)={tex(sp.factor(sp.diff(f, x)))}=0$",
            f"إذن {answer}",
        ),
        "R",
        {"type": "zeros", "f": f, "points": [p, q], "low": p - 3, "high": q + 3},
        wrong_kinds=kinds,
    )


@variant("2.4", example=4)
def derivative_from_values(rng: random.Random) -> Problem:
    a = rng.randint(-2, 3)
    fa, dfa, ga, dga = nz(rng, -5, 5), rng.randint(-4, 5), nz(rng, -4, 4), rng.randint(-4, 4)
    f_real, g_real = fa + dfa * (x - a), ga + dga * (x - a)
    quotient = rng.random() < 0.4
    if quotient:
        value = sp.Rational(dfa * ga - fa * dga, ga**2)
        expr, real, level = r"\left(\dfrac{f}{g}\right)'", f_real / g_real, "A"
        rule = rf"$\dfrac{{f'g-fg'}}{{g^2}}=\dfrac{{({dfa})({ga})-({fa})({dga})}}{{({ga})^2}}$"
        pool = [
            ("sign", sp.Rational(fa * dga - dfa * ga, ga**2)),
            ("formula", sp.Rational(dfa, dga) if dga else value + 2),
            ("nearby", value + 1),
        ]
    else:
        value = sp.Integer(dfa * ga + fa * dga)
        expr, real, level = r"(f\cdot g)'", f_real * g_real, "K"
        rule = f"$f'g+fg'=({dfa})({ga})+({fa})({dga})$"
        pool = [
            ("formula", sp.Integer(dfa * dga)),
            ("sign", sp.Integer(dfa * ga - fa * dga)),
            ("formula", sp.Integer(fa * ga)),
        ]
    wrong, kinds = tagged_wrongs(value, *pool)
    return Problem(
        "2.4",
        f"إذا كان $f({a})={fa}$ و$f'({a})={dfa}$ و$g({a})={ga}$ و$g'({a})={dga}$ فأوجد ${expr}({a})$.",
        m(value),
        wrong,
        (rule, f"$={tex(value)}$"),
        level,
        {"type": "derivative", "f": real, "at": a, "value": value},
        wrong_kinds=kinds,
    )


@variant("2.4", example=3)
def quotient_constant(rng: random.Random) -> Problem:
    c = nz(rng, -3, 3)
    v = nz(rng, -3, 3)
    k = c - v * c**2
    h = (x + k) / (x + c)
    k_sym = sp.Symbol("k")
    wrong, kinds = tagged_wrongs(
        sp.Integer(k),
        ("formula", sp.Integer(c + v * c**2)),
        ("formula", sp.Integer(v * c**2)),
        ("sign", sp.Integer(-k)),
    )
    return Problem(
        "2.4",
        f"إذا كانت $h(x)={frac(x + k_sym, x + c)}$ و$h'(0)={v}$ فأوجد قيمة الثابت $k$.",
        m(k),
        wrong,
        (
            rf"$h'(x)=\dfrac{{(x{c:+d})-(x+k)}}{{(x{c:+d})^2}}=\dfrac{{{c}-k}}{{(x{c:+d})^2}}$",
            rf"$h'(0)=\dfrac{{{c}-k}}{{{c**2}}}={v}$ فإن $k={k}$",
        ),
        "R",
        {"type": "derivative", "f": h, "at": 0, "value": sp.Integer(v)},
        wrong_kinds=kinds,
    )


@variant("2.5", example=1)
def chain_given_inner(rng: random.Random) -> Problem:
    n = rng.choice([2, 3, 4, 5])
    a, b = nz(rng, -4, 5), nz(rng, -6, 6)
    inner = a * x + b
    f = inner**n
    d = n * a * inner ** (n - 1)
    u = sp.Symbol("u")
    wrong, kinds = tagged_wrongs(
        d,
        ("partial", n * inner ** (n - 1)),
        ("formula", n * a * inner**n),
        ("partial", a * inner ** (n - 1)),
    )
    return Problem(
        "2.5",
        f"إذا كانت $y=u^{n}$ و$u={tex(inner)}$ فأوجد $\\dfrac{{dy}}{{dx}}$.",
        m(d),
        wrong,
        (
            rf"$\dfrac{{dy}}{{dx}}=\dfrac{{dy}}{{du}}\cdot\dfrac{{du}}{{dx}}={tex(n * u ** (n - 1))}\cdot {a}$",
            f"$={tex(d)}$",
        ),
        "K",
        {"type": "function", "f": f, "d": d, "order": 1},
        wrong_kinds=kinds,
    )


@variant("2.5", example=2)
def chain_from_values(rng: random.Random) -> Problem:
    a, b = rng.randint(-2, 3), rng.randint(-3, 3)
    dg, df = nz(rng, -4, 4), nz(rng, -4, 4)
    g_real = b + dg * (x - a)
    f_outer = df * (x - b) + rng.randint(-5, 5) + (x - b) ** 2  # f'(b)=df
    composite = f_outer.subs(x, g_real)
    value = df * dg
    wrong, kinds = tagged_wrongs(
        sp.Integer(value),
        ("formula", sp.Integer(df + dg)),
        ("concept", sp.Integer(df * b)),
        ("concept", sp.Integer(dg * b)),
    )
    return Problem(
        "2.5",
        f"إذا كان $g({a})={b}$ و$g'({a})={dg}$ و$f'({b})={df}$ فأوجد $(f\\circ g)'({a})$.",
        m(value),
        wrong,
        (rf"$(f\circ g)'({a})=f'(g({a}))\cdot g'({a})=f'({b})\cdot g'({a})$", f"$=({df})({dg})={value}$"),
        "R",
        {"type": "derivative", "f": composite, "at": a, "value": sp.Integer(value)},
        wrong_kinds=kinds,
    )


@variant("2.6", example=1)
def derivative_exp_log_simple(rng: random.Random) -> Problem:
    if rng.random() < 0.5:
        a, b = nz(rng, -5, 5), nz(rng, -4, 4)
        f, d, positive = a * sp.exp(b * x), a * b * sp.exp(b * x), False
        pool = [
            ("partial", a * sp.exp(b * x)),
            ("partial", b * sp.exp(b * x)),
            ("formula", a * b * sp.exp(x)),
        ]
    else:
        a, b = nz(rng, 2, 6), nz(rng, 2, 7)
        f, d, positive = a * sp.log(b * x), sp.Integer(a) / x, True
        pool = [
            ("formula", sp.Integer(a) / (b * x)),
            ("formula", sp.Integer(a * b) / x),
            ("partial", sp.Integer(b) / x),
        ]
    wrong, kinds = tagged_wrongs(d, *pool)
    return Problem(
        "2.6",
        f"أوجد $f'(x)$ للدالة $f(x)={tex(f)}$.",
        m(d),
        wrong,
        (r"$(e^{kx})'=ke^{kx}$ و$(\ln kx)'=\dfrac{1}{x}$", f"$f'(x)={tex(d)}$"),
        "K",
        {"type": "function", "f": f, "d": d, "order": 1, "positive": positive},
        wrong_kinds=kinds,
    )


@variant("2.6", example=2)
def exponential_horizontal_tangent(rng: random.Random) -> Problem:
    a = rng.choice([-2, -1, 1, 2, sp.Rational(1, 2), sp.Rational(-1, 2)])
    c = nz(rng, -3, 3)
    f = c * x * sp.exp(a * x)
    point = -1 / sp.Integer(1) / a
    wrong, kinds = tagged_wrongs(
        f"$x={tex(point)}$",
        ("sign", f"$x={tex(-point)}$"),
        ("concept", f"$x={tex(a)}$"),
        ("concept", "$x=0$"),
        ("nearby", f"$x={tex(point + 1)}$"),
        ("formula", f"$x={tex(2 * point)}$"),
    )
    return Problem(
        "2.6",
        f"أوجد قيمة $x$ التي يكون عندها المماس لمنحنى $f(x)={tex(f)}$ أفقيًا.",
        f"$x={tex(point)}$",
        wrong,
        (
            f"$f'(x)={tex(sp.factor(sp.diff(f, x)))}$",
            r"$e^{kx}>0$ دائمًا، فالمشتقة تنعدم عندما ينعدم العامل الخطي.",
            f"$x={tex(point)}$",
        ),
        "R",
        {"type": "zeros", "f": f, "points": [point], "low": -6, "high": 6},
        wrong_kinds=kinds,
    )


@variant("2.7", example=1)
def derivative_trig_simple(rng: random.Random) -> Problem:
    a, b = nz(rng, -5, 5), nz(rng, -5, 5)
    f = a * sp.sin(x) + b * sp.cos(x)
    d = sp.diff(f, x)
    wrong, kinds = tagged_wrongs(
        d,
        ("sign", a * sp.cos(x) + b * sp.sin(x)),
        ("sign", -a * sp.cos(x) + b * sp.sin(x)),
        ("formula", a * sp.cos(x) - b * sp.cos(x)),
    )
    return Problem(
        "2.7",
        f"أوجد $f'(x)$ للدالة $f(x)={tex(f)}$.",
        m(d),
        wrong,
        (r"$(\sin x)'=\cos x$ و$(\cos x)'=-\sin x$", f"$f'(x)={tex(d)}$"),
        "K",
        {"type": "function", "f": f, "d": d, "order": 1},
        wrong_kinds=kinds,
    )


TRIG_TANGENTS = [  # (الدالة، النقاط في [0,π]) نقاط المماس الأفقي
    (x + 2 * sp.cos(x), [sp.pi / 6, 5 * sp.pi / 6]),
    (x - 2 * sp.sin(x), [sp.pi / 3]),
    (sp.sin(x) + sp.cos(x), [sp.pi / 4]),
    (sp.sqrt(3) * x + 2 * sp.cos(x), [sp.pi / 3, 2 * sp.pi / 3]),
    (sp.sin(x) - sp.cos(x), [3 * sp.pi / 4]),
]


@variant("2.7", example=5)
def trig_horizontal_tangent(rng: random.Random) -> Problem:
    base, points = rng.choice(TRIG_TANGENTS)
    f = rng.choice([1, 2, 3, -1, -2]) * base  # الضرب في ثابت لا يغيّر نقاط المماس الأفقي
    answer = joined(points)
    others = [sp.pi / 6, sp.pi / 4, sp.pi / 3, sp.pi / 2, 2 * sp.pi / 3, 3 * sp.pi / 4, 5 * sp.pi / 6]
    distractors = [joined([p]) for p in others if p not in points][:4]
    wrong, kinds = tagged_wrongs(answer, *(("concept", d) for d in distractors))
    return Problem(
        "2.7",
        rf"أوجد قيم $x$ في الفترة $[0,\pi]$ التي يكون عندها المماس لمنحنى $f(x)={tex(f)}$ أفقيًا.",
        answer,
        wrong,
        (f"$f'(x)={tex(sp.diff(f, x))}=0$", f"في الفترة $[0,\\pi]$: {answer}"),
        "R",
        {"type": "zeros", "f": f, "points": points, "low": 0, "high": sp.pi},
        wrong_kinds=kinds,
    )


@variant("2.8", example=1)
def implicit_ellipse_expression(rng: random.Random) -> Problem:
    a, b = rng.randint(1, 4), rng.randint(1, 4)
    c = rng.randint(5, 30)
    F = a * x**2 + b * y**2 - c
    expr = -sp.Rational(a, b) * x / y
    wrong, kinds = tagged_wrongs(
        expr,
        ("sign", -expr),
        ("swap", -sp.Rational(b, a) * x / y),
        ("swap", -sp.Rational(a, b) * y / x),
    )
    return Problem(
        "2.8",
        f"أوجد $\\dfrac{{dy}}{{dx}}$ للعلاقة ${tex(a * x**2 + b * y**2)}={c}$.",
        m(expr),
        wrong,
        (f"نشتق الطرفين: ${2 * a}x+{2 * b}y\\,y'=0$", f"$y'={tex(expr)}$"),
        "K",
        {"type": "implicit_expr", "F": F, "expr": expr, "c": c, "a": a, "b": b},
        wrong_kinds=kinds,
    )


@variant("2.9", example=2)
def second_derivative_simple(rng: random.Random) -> Problem:
    a, b, c = nz(rng, -4, 4), nz(rng, -5, 5), rng.randint(-6, 6)
    f = a * x**3 + b * x**2 + c * x
    d2 = sp.diff(f, x, 2)
    wrong, kinds = tagged_wrongs(
        d2,
        ("concept", sp.diff(f, x)),
        ("formula", d2 + c),
        ("partial", sp.expand(3 * a * x + 2 * b)),
    )
    return Problem(
        "2.9",
        f"أوجد $f''(x)$ للدالة $f(x)={tex(f)}$.",
        m(d2),
        wrong,
        (f"$f'(x)={tex(sp.diff(f, x))}$", f"$f''(x)={tex(d2)}$"),
        "K",
        {"type": "function", "f": f, "d": d2, "order": 2},
        wrong_kinds=kinds,
    )


@variant("2.9", example=5)
def motion_velocity_acceleration(rng: random.Random) -> Problem:
    t = sp.Symbol("t")
    b, c = rng.randint(-6, 3), rng.randint(-9, 9)
    s = t**3 + b * t**2 + c * t + rng.randint(0, 9)
    t0 = rng.randint(1, 4)
    want_acc = rng.random() < 0.5
    order = 2 if want_acc else 1
    value = sp.diff(s, t, order).subs(t, t0)
    word = "التسارع" if want_acc else "السرعة"
    other = sp.diff(s, t, 3 - order).subs(t, t0)
    wrong, kinds = tagged_wrongs(
        value,
        ("concept", other),
        ("concept", s.subs(t, t0)),
        ("nearby", value + 2),
    )
    return Problem(
        "2.9",
        f"يتحرك جسم في خط مستقيم وفق $s(t)={tex(s)}$ حيث $s$ بالأمتار و$t$ بالثواني. أوجد {word} عند $t={t0}$.",
        m(value),
        wrong,
        (
            f"$v(t)=s'(t)={tex(sp.diff(s, t))}$",
            f"$a(t)=v'(t)={tex(sp.diff(s, t, 2))}$",
            f"{word} عند $t={t0}$ تساوي ${tex(value)}$",
        ),
        "A",
        {"type": "derivative", "f": s.subs(t, x), "at": t0, "order": order, "value": value},
        wrong_kinds=kinds,
    )


@variant("2.9", example=5)
def motion_at_rest(rng: random.Random) -> Problem:
    p = rng.randint(1, 3)
    q = p + rng.choice([2, 4])
    t = sp.Symbol("t")
    k = rng.choice([1, 2, sp.Rational(1, 3), sp.Rational(2, 3)])  # يغيّر الدالة لا أزمنة السكون
    s = sp.expand(k * (t**3 - sp.Rational(3 * (p + q), 2) * t**2 + 3 * p * q * t) + rng.randint(0, 9))
    answer = f"$t={p}$ و$t={q}$"
    wrong, kinds = tagged_wrongs(
        answer,
        ("partial", f"$t={p}$ فقط"),
        ("partial", f"$t={q}$ فقط"),
        ("formula", f"$t={tex(sp.Rational(p + q, 2))}$"),
        ("concept", "$t=0$"),
    )
    return Problem(
        "2.9",
        f"يتحرك جسم وفق $s(t)={tex(s)}$ حيث $t\\ge0$. متى يكون الجسم في حالة سكون لحظي؟",
        answer,
        wrong,
        (
            "السكون حيث السرعة صفر: $v(t)=s'(t)=0$.",
            f"$v(t)={tex(sp.factor(sp.diff(s, t)))}=0$",
            f"إذن {answer}",
        ),
        "R",
        {"type": "zeros", "f": s.subs(t, x), "points": [p, q], "low": 0, "high": 12},
        wrong_kinds=kinds,
    )


# الوحدة الثالثة
@variant("3.1", example=2)
def critical_numbers(rng: random.Random) -> Problem:
    f, p, q, _ = cubic_with_critical_points(rng)
    answer = joined([p, q])
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", joined([-p, -q])),
        ("partial", joined([p])),
        ("partial", joined([q])),
        ("concept", joined([0])),
    )
    return Problem(
        "3.1",
        f"أوجد الأعداد الحرجة للدالة $f(x)={tex(f)}$.",
        answer,
        wrong,
        (
            "الأعداد الحرجة حيث $f'(x)=0$ أو غير معرفة.",
            f"$f'(x)={tex(sp.factor(sp.diff(f, x)))}=0$",
            f"إذن {answer}",
        ),
        "K",
        {"type": "zeros", "f": f, "points": [p, q], "low": p - 3, "high": q + 3},
        wrong_kinds=kinds,
    )


@variant("3.2", example=2)
def extremum_from_linear_derivative(rng: random.Random) -> Problem:
    p = rng.randint(-4, 4)
    s = nz(rng, -3, 3)
    fprime = s * (x - p)
    f = s * (x - p) ** 2 / 2
    is_min = s > 0
    answer = f"قيمة {'صغرى' if is_min else 'عظمى'} محلية عند $x={p}$"
    wrong, kinds = tagged_wrongs(
        answer,
        ("direction", f"قيمة {'عظمى' if is_min else 'صغرى'} محلية عند $x={p}$"),
        ("sign", f"قيمة {'صغرى' if is_min else 'عظمى'} محلية عند $x={-p if p else 1}$"),
        ("concept", "لا توجد قيمة قصوى"),
    )
    return Problem(
        "3.2",
        f"إذا كانت $f'(x)={tex(fprime)}$ فما نوع القيمة القصوى المحلية للدالة $f$ وأين تقع؟",
        answer,
        wrong,
        (
            f"$f'(x)=0$ عند $x={p}$.",
            f"إشارة $f'$ تتغير من {'سالبة إلى موجبة' if is_min else 'موجبة إلى سالبة'} عند $x={p}$.",
        ),
        "K",
        {"type": "local", "f": f, "at": p, "value": 0, "max": not is_min},
        wrong_kinds=kinds,
    )


@variant("3.3", example=3)
def concavity_from_second_derivative(rng: random.Random) -> Problem:
    h = rng.randint(-4, 4)
    a = nz(rng, -3, 3)
    second = a * (x - h)
    f = a * (x - h) ** 3 / 6
    up_right = a > 0
    ask_up = rng.choice([True, False])
    right_side = ask_up == up_right
    answer = f"$({h},\\infty)$" if right_side else f"$(-\\infty,{h})$"
    word = "أعلى" if ask_up else "أسفل"
    wrong, kinds = tagged_wrongs(
        answer,
        ("direction", f"$({h},\\infty)$"),
        ("direction", f"$(-\\infty,{h})$"),
        ("sign", f"$(-\\infty,{-h})$" if h else "$(-\\infty,1)$"),
        ("concept", "$(-\\infty,\\infty)$"),
    )
    return Problem(
        "3.3",
        f"إذا كانت $f''(x)={tex(second)}$ فحدد الفترة التي يكون فيها منحنى $f$ مقعرًا إلى {word}.",
        answer,
        wrong,
        (f"$f''(x)=0$ عند $x={h}$.", f"التقعر إلى {word} حيث $f''(x){'>' if ask_up else '<'}0$: {answer}"),
        "K",
        {"type": "concavity", "f": f, "at": h, "right_side": right_side, "up": ask_up},
        wrong_kinds=kinds,
    )


DECLINE_CONTEXTS = (
    ("عدد زوار معرض", "ساعة", "افتتاحه", "عدد الزوار", False),
    ("منسوب الماء في خزان بالسنتيمتر", "دقيقة", "فتح الصمام", "المنسوب", False),
    ("عدد مشاهدي بث مباشر", "دقيقة", "بدايته", "عدد المشاهدين", False),
    ("مبيعات متجر بالريال", "يومًا", "بدء الحملة", "المبيعات", True),
)


@variant("3.1", example=2)
def decline_start(rng: random.Random) -> Problem:
    """نموذج تطبيقي: N'(t) = -3(t-q)(t+p)، فيتزايد حتى t=q ثم يتناقص داخل المجال."""
    p = rng.randint(1, 5)
    q = p + 2 * rng.randint(0, 3) + rng.choice([0, 2]) or 2
    end = q + rng.randint(2, 4)
    model = -(x**3) + sp.Rational(3, 2) * (q - p) * x**2 + 3 * p * q * x
    start = 10 * rng.randint(2, 12)
    start = max(start, 10 * (int(-model.subs(x, end)) // 10 + 2))
    model = sp.expand(model + start)
    quantity, unit, since, name, feminine = rng.choice(DECLINE_CONTEXTS)
    modelled, begins = ("تُنمذَج", "تبدأ") if feminine else ("يُنمذَج", "يبدأ")
    t = sp.Symbol("t")
    shown, derivative = model.subs(x, t), sp.factor(sp.diff(model, x)).subs(x, t)
    answer = f"$t={q}$"
    wrong, kinds = tagged_wrongs(
        answer,
        ("concept", f"$t={p}$" if p != q else f"$t={q + 1}$"),
        ("concept", f"$t={end}$"),
        ("concept", "$t=0$"),
        ("nearby", f"$t={q - 1}$"),
    )
    return Problem(
        "3.1",
        f"{modelled} {quantity} بعد $t$ {unit} من {since} بالدالة $N(t)={tex(shown)}$ حيث $0\\le t\\le {end}$. "
        f"عند أي قيمة للزمن $t$ {begins} {name} بالتناقص؟ برر إجابتك.",
        answer,
        wrong,
        (
            f"$N'(t)={tex(derivative)}$",
            f"داخل المجال $N'(t)=0$ عند $t={q}$ فقط، لأن $t=-{p}$ خارج المجال.",
            f"$N'(t)>0$ على $(0,{q})$ و$N'(t)<0$ على $({q},{end})$.",
            f"إذن {begins} {name} بالتناقص عند {answer}.",
        ),
        "R",
        {"type": "turning", "f": model, "at": q, "low": 0, "high": end},
        wrong_kinds=kinds,
    )


SURFACE_SHAPES = (
    ("صندوق مفتوح من الأعلى", False),
    ("صندوق مغلق", True),
    ("خزان على شكل متوازي مستطيلات مفتوح من الأعلى", False),
    ("علبة مغلقة على شكل متوازي مستطيلات", True),
)


@variant("3.5", example=3)
def surface_in_one_variable(rng: random.Random) -> Problem:
    """المهارة السابقة لمسائل القيم المثلى: التعويض من قيد الحجم لكتابة الدالة بمتغير واحد."""
    volume = 4 * rng.randint(2, 60)
    shape, closed = rng.choice(SURFACE_SHAPES)
    bases = 2 if closed else 1
    surface = bases * x**2 + sp.Rational(4 * volume) / x
    answer = f"$S(x)={tex(surface)}$"
    other = (3 - bases) * x**2 + sp.Rational(4 * volume) / x
    wrong, kinds = tagged_wrongs(
        answer,
        ("concept", f"$S(x)={tex(other)}$"),
        ("formula", f"$S(x)={tex(bases * x**2 + sp.Rational(volume) / x)}$"),
        ("formula", f"$S(x)={tex(bases * x**2 + sp.Rational(4 * volume) / x**2)}$"),
    )
    return Problem(
        "3.5",
        f"{shape} قاعدته مربعة طول ضلعها $x$ سم وحجمه ${volume}$ سم³. "
        "اكتب المساحة السطحية $S$ بدلالة $x$ فقط.",
        answer,
        wrong,
        (
            f"إذا كان الارتفاع $h$ فالحجم $x^2h={volume}$، ومنه $h={tex(sp.Rational(volume) / x**2)}$.",
            f"المساحة السطحية: {'قاعدتان' if closed else 'قاعدة واحدة'} وأربعة أوجه جانبية، "
            f"أي $S={tex(bases * x**2)}+4xh$.",
            f"بالتعويض عن $h$: {answer}",
        ),
        "K",
        {"type": "surface", "S": surface, "volume": volume, "closed": closed},
        wrong_kinds=kinds,
    )
