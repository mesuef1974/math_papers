"""كل جواب يُتحقق منه عدديًا بطريقة مستقلة عن طريقة بنائه، عبر بذور كثيرة."""

import math
import operator
import random
from fractions import Fraction

import mpmath
import pytest
import sympy as sp

from apps.papers.domain.generators import NO_LIMIT, REGISTRY, available_lessons, x, y
from apps.papers.domain.graphs import value_at

SEEDS = range(120)
ALL = [(lesson, fn) for (_, lesson), fns in REGISTRY.items() for fn in fns]
IDS = [fn.__name__ for _, fn in ALL]
TOL = 1e-6


def number(expr, at):
    return float(sp.N(expr.subs(x, at), 40))


def fn(expr):
    return sp.lambdify(x, expr, "mpmath")


def assert_limit(c):
    h = sp.Rational(1, 10**7)
    at = c["at"]
    if at == sp.oo:
        estimate = number(c["expr"], sp.Integer(10) ** 9)
    else:
        estimate = (number(c["expr"], at + h) + number(c["expr"], at - h)) / 2
    assert estimate == pytest.approx(float(c["value"]), abs=1e-5)


def assert_derivative(c):
    mpmath.mp.dps = 40
    got = mpmath.diff(fn(c["f"]), mpmath.mpf(int(c["at"])), c.get("order", 1))
    assert float(got) == pytest.approx(float(c["value"]), abs=TOL)


def assert_function(c):
    mpmath.mp.dps = 40
    points = (0.3, 0.7, 1.3) if c.get("positive") else (-0.4, 0.3, 0.7)
    for point in points:
        got = mpmath.diff(fn(c["f"]), mpmath.mpf(point), c["order"])
        want = float(sp.N(c["d"].subs(x, sp.Float(point, 40))))
        assert float(got) == pytest.approx(want, rel=1e-6, abs=TOL)


def assert_implicit(c):
    F = sp.lambdify((x, y), c["F"], "mpmath")
    mpmath.mp.dps = 40
    p, q = c["point"]
    assert c["F"].subs({x: p, y: q}) == 0
    h = mpmath.mpf(10) ** -8
    near = [mpmath.findroot(lambda v, s=s: F(p + s, v), q) for s in (h, -h)]
    assert float((near[0] - near[1]) / (2 * h)) == pytest.approx(float(c["value"]), abs=1e-5)


def samples(low, high, count=801):
    low, high = float(low), float(high)
    return [low + (high - low) * i / (count - 1) for i in range(count)]


def assert_monotonic(c):
    d = sp.lambdify(x, sp.diff(c["f"], x))
    p, q = c["p"], c["q"]
    inner, outer = d((p + q) / 2), d(q + 1)
    assert inner * outer < 0 and d(p - 1) * outer > 0
    assert (inner > 0) == c["inner_increasing"]
    assert c["answer_inner"] == (c["ask"] == (inner > 0))


def assert_local(c):
    f, at = sp.lambdify(x, c["f"]), c["at"]
    assert f(at) == pytest.approx(float(c["value"]))
    sides = (f(at - 0.01), f(at + 0.01))
    assert all(v < f(at) for v in sides) if c["max"] else all(v > f(at) for v in sides)


def assert_absolute(c):
    f = sp.lambdify(x, c["f"])
    values = [f(v) for v in samples(c["low"], c["high"])]
    assert (max(values) if c["max"] else min(values)) == pytest.approx(float(c["value"]), abs=1e-3)


def assert_inflection(c):
    d2, at = sp.lambdify(x, sp.diff(c["f"], x, 2)), c["at"]
    assert d2(at - 1) * d2(at + 1) < 0
    assert number(c["f"], at) == pytest.approx(float(c["value"]))


def assert_concavity(c):
    d2 = sp.lambdify(x, sp.diff(c["f"], x, 2))
    side = c["at"] + (1 if c["right_side"] else -1)
    assert (d2(side) > 0) == c["up"]


def assert_optimum(c):
    f = sp.lambdify(x, c["f"])
    values = [f(v) for v in samples(c["low"], c["high"], 4001)]
    best = max(values) if c["max"] else min(values)
    assert best == pytest.approx(float(c["value"]), rel=1e-3)
    assert f(float(c["arg"])) == pytest.approx(float(c["value"]))


def assert_turning(c):
    """الدالة تتزايد حتى النقطة ثم تتناقص بعدها على المجال كله، فأكبر قيمها عندها (من القيم لا من المشتقة)."""
    f = sp.lambdify(x, c["f"])
    xs = samples(c["low"], c["high"], 2001)
    values = [f(v) for v in xs]
    peak = max(range(len(xs)), key=values.__getitem__)
    assert xs[peak] == pytest.approx(float(c["at"]), abs=(c["high"] - c["low"]) / 1000)
    assert 0 < peak < len(xs) - 1
    assert all(a < b for a, b in zip(values[:peak], values[1 : peak + 1], strict=False))
    assert all(a > b for a, b in zip(values[peak:], values[peak + 1 :], strict=False))


def assert_surface(c):
    """المساحة من الهندسة مباشرة: الارتفاع من الحجم، ثم القواعد والأوجه الأربعة."""
    s = sp.lambdify(x, c["S"])
    for side in (0.5, 1.0, 2.5, 7.0):
        height = c["volume"] / side**2
        direct = (2 if c["closed"] else 1) * side**2 + 4 * side * height
        assert s(side) == pytest.approx(direct)


def assert_one_sided(c):
    left, right = c["left"].subs(x, c["at"]), c["right"].subs(x, c["at"])
    assert (left == right) == (c["value"] is not None)
    if c["value"] is not None:
        assert left == c["value"]


def assert_continuity(c):
    assert c["left"].subs(x, c["at"]) == c["right"].subs(x, c["at"])


def assert_average(c):
    f = sp.lambdify(x, c["f"])
    assert (f(c["b"]) - f(c["a"])) / (c["b"] - c["a"]) == pytest.approx(float(c["value"]))


def assert_graph_limit(c):
    """الجواب يُقرأ من الرسم المرسوم فعلًا: المنحنيات قرب c والنقاط المغلقة."""
    graph, at, eps = c["graph"], c["at"], 1e-3
    left = value_at(graph, at - eps)
    right = value_at(graph, at + eps)
    assert len(left) == 1 and len(right) == 1
    assert left[0] == pytest.approx(c["left"], abs=0.01) and right[0] == pytest.approx(c["right"], abs=0.01)
    closed = [py for px, py, is_closed in graph["dots"] if is_closed and px == at]
    expected = {
        "both": f"${c['left']}$" if c["left"] == c["right"] else NO_LIMIT,
        "left": f"${c['left']}$",
        "right": f"${c['right']}$",
        "value": f"${int(closed[0])}$" if closed else "غير معرفة",
    }[c["ask"]]
    assert c["answer"] == expected


def one(graph, px):
    values = value_at(graph, px)
    return values[0] if len(values) == 1 else None


def assert_graph_discontinuity(c):
    graph, at = c["graph"], c["at"]
    if c["kind"] == "infinite":
        assert at in graph["asymptotes"]
        near = [v for s in (-0.03, 0.03) for v in value_at(graph, at + s)]
        assert all(abs(v) > 3 for v in near)
        return
    left, right = one(graph, at - 1e-3), one(graph, at + 1e-3)
    assert left == pytest.approx(c["left"], abs=0.01) and right == pytest.approx(c["right"], abs=0.01)
    if c["kind"] == "jump":
        assert c["left"] != c["right"]
    else:
        assert c["left"] == c["right"]
        assert [at, c["left"], False] in [list(d) for d in graph["dots"]]
        assert not any(closed and py == c["left"] for px, py, closed in graph["dots"] if px == at)


def assert_graph_tangent(c):
    graph, at = c["graph"], c["at"]
    (x0, y0), (x1, y1) = graph["lines"][0]
    assert (y1 - y0) / (x1 - x0) == pytest.approx(c["value"])
    h = 0.5
    slope = (one(graph, at + h) - one(graph, at - h)) / (2 * h)
    assert slope == pytest.approx(c["value"], abs=0.02)
    assert one(graph, at) == pytest.approx(c["y"], abs=0.01)


def sign_at(graph, px):
    value = one(graph, px)
    assert value is not None and abs(value) > 1e-6
    return value > 0


def assert_graph_sign(c):
    graph, p, q = c["graph"], c["p"], c["q"]
    inner = sign_at(graph, (p + q) / 2)
    assert sign_at(graph, q + 0.5) != inner and sign_at(graph, p - 0.5) != inner
    assert c["answer_inner"] == (c["positive"] == inner)


def sign_changes(graph):
    xs = [-4.93 + 0.05 * i for i in range(197)]
    signs = [(px, v > 0) for px in xs if (v := one(graph, px)) is not None and abs(v) > 1e-4]
    found = {"max": [], "min": []}
    for (xa, sa), (xb, sb) in zip(signs, signs[1:], strict=False):
        if sa != sb:
            found["max" if sa else "min"].append(round((xa + xb) / 2))
    return found


def assert_graph_extremum(c):
    found = sign_changes(c["graph"])["max" if c["max"] else "min"]
    assert c["answer"] == (f"$x={found[0]}$" if found else "لا توجد")


def assert_graph_concavity(c):
    graph, h = c["graph"], c["h"]
    assert one(graph, h - 1) == pytest.approx(one(graph, h + 1), abs=0.01)
    rising_right = one(graph, h + 1) > one(graph, h + 0.5)
    expected = {
        "inflection": f"$x={h}$",
        "up": rf"$({h},\infty)$" if rising_right else rf"$(-\infty,{h})$",
        "down": rf"$(-\infty,{h})$" if rising_right else rf"$({h},\infty)$",
    }[c["ask"]]
    assert c["answer"] == expected


def assert_graph_options(c):
    """الخيار الأول يوافق إشارة f′ المرسومة في كل نقطة، وكل خيار آخر يخالفها في نقطة على الأقل."""
    xs = [-4.5 + 0.25 * i for i in range(37)]

    def agrees(option):
        mismatches = 0
        for px in xs:
            d, a, b = one(c["graph"], px), one(option, px - 0.05), one(option, px + 0.05)
            if None in (d, a, b) or abs(d) < 0.3:
                continue
            mismatches += (b > a) != (d > 0)
        return mismatches == 0

    first, *others = c["options"]
    assert agrees(first)
    assert not any(agrees(option) for option in others)


def assert_continuity_bool(c):
    at = c["at"]
    left, right = c["left"].subs(x, at), c["right"].subs(x, at)
    assert (left == right) == c["continuous"]


def assert_continuity2(c):
    p, q = c["p"], c["q"]
    assert c["left"].subs(x, p) == c["mid"].subs(x, p)
    assert c["mid"].subs(x, q) == c["right"].subs(x, q)


def assert_differentiable(c):
    at = c["at"]
    assert c["left"].subs(x, at) == c["right"].subs(x, at)
    mpmath.mp.dps = 30
    h = mpmath.mpf(10) ** -10
    left_d = (fn(c["left"])(at) - fn(c["left"])(at - h)) / h
    right_d = (fn(c["right"])(at + h) - fn(c["right"])(at)) / h
    assert (abs(left_d - right_d) < 1e-6) == c["answer"]


def assert_avg_instant(c):
    f = sp.lambdify(x, c["f"])
    average = (f(c["b"]) - f(c["a"])) / (c["b"] - c["a"])
    assert float(mpmath.diff(fn(c["f"]), float(c["point"]))) == pytest.approx(average)
    assert c["a"] < c["point"] < c["b"]


def assert_tangent(c):
    mpmath.mp.dps = 30
    at = c["at"]
    assert float(mpmath.diff(fn(c["f"]), at)) == pytest.approx(float(c["slope"]), abs=TOL)
    assert number(c["f"], at) == pytest.approx(float(c["slope"] * at + c["intercept"]))


def assert_zeros(c):
    """المشتقة تنعدم عند النقاط المعطاة، ولا تتغير إشارتها في الفترة إلا عندها."""
    mpmath.mp.dps = 30
    d = fn(sp.diff(c["f"], x))
    for point in c["points"]:
        assert abs(float(d(float(point)))) < 1e-9
    xs = samples(c["low"], c["high"], 3001)
    signs = [float(d(v)) > 0 for v in xs if abs(float(d(v))) > 1e-9]
    changes = sum(a != b for a, b in zip(signs, signs[1:], strict=False))
    assert changes == len(c["points"])


def assert_implicit_expr(c):
    """نقطة على المنحنى عدديًا، ثم ميل المنحنى بالفروق مقارنة بالعبارة."""
    a, b, k = c["a"], c["b"], c["c"]
    x0 = mpmath.sqrt(k / a) / 3
    upper = lambda v: mpmath.sqrt((k - a * v**2) / b)  # noqa: E731
    y0 = upper(x0)
    h = mpmath.mpf(10) ** -8
    slope = (upper(x0 + h) - upper(x0 - h)) / (2 * h)
    assert float(c["expr"].subs({x: x0, y: y0})) == pytest.approx(float(slope), abs=1e-6)


def assert_shape_signs(c):
    """الدالة الشاهدة تحقق الإشارتين على الفترة كلها عدديًا."""
    mpmath.mp.dps = 30
    f = fn(c["f"])
    for v in samples(c["low"] + 0.01, c["high"] - 0.01, 101):
        assert (float(mpmath.diff(f, v, 1)) > 0) == c["increasing"]
        assert (float(mpmath.diff(f, v, 2)) > 0) == c["up"]


def assert_second_derivative_test(c):
    f, at = sp.lambdify(x, c["f"]), c["at"]
    mpmath.mp.dps = 30
    assert abs(float(mpmath.diff(fn(c["f"]), at, 1))) < 1e-9
    sides = (f(at - 0.5), f(at + 0.5))
    assert all(v < f(at) for v in sides) if c["max"] else all(v > f(at) for v in sides)


def assert_sketch_summary(c):
    f, d2 = sp.lambdify(x, c["f"]), sp.lambdify(x, sp.diff(c["f"], x, 2))
    for at, is_max in ((c["max_at"], True), (c["min_at"], False)):
        sides = (f(at - 0.05), f(at + 0.05))
        assert all(v < f(at) for v in sides) if is_max else all(v > f(at) for v in sides)
    t = c["inflection"]
    assert d2(t - 0.5) * d2(t + 0.5) < 0 and abs(d2(t)) < 1e-9


def assert_graph_shape(c):
    """في الفترة: إشارة f′ المرسومة وميلها يوافقان الشكل؛ وخارجها مباشرة يختل أحدهما."""
    graph = c["graph"]
    low, high = c["low"], 5 if c["high"] is None else c["high"]

    def fits(px):
        value, before, after = one(graph, px), one(graph, px - 0.05), one(graph, px + 0.05)
        if None in (value, before, after):
            return None  # المنحنى مقصوص خارج النافذة هنا
        return (value > 0) == c["increasing"] and (after > before) == c["up"]

    verdicts = [v for px in samples(low + 0.1, high - 0.1, 41) if (v := fits(px)) is not None]
    assert len(verdicts) >= 5 and all(verdicts)
    assert fits(low - 0.2) is False
    if c["high"] is not None:
        assert fits(high + 0.2) is False


def assert_value(c):
    """قيمة الدالة عند النقطة: المنحنى يمر بالنقطة المعطاة، أو التعويض يعطي الجواب."""
    assert number(c["f"], c["at"]) == pytest.approx(float(c["value"]))


def assert_parabola_shape(c):
    """اتجاه الفتحة والاتساع من قيم الدالة نفسها مقارنةً بقيم x² عند النقطة ذاتها."""
    answer, at_two = c["answer"], number(c["f"], 2)
    assert ("الأعلى" in answer) == (at_two > number(c["f"], 0))
    assert ("أضيق" in answer) == (abs(at_two) > 4)
    assert ("الأعلى" in answer) != ("الأسفل" in answer) and ("أضيق" in answer) != ("أوسع" in answer)


def assert_parabola_monotone(c):
    rising_right = number(c["f"], 2) > number(c["f"], 1)
    assert rising_right != (number(c["f"], -1) > number(c["f"], -2))
    assert c["answer"] == ("$x>0$" if rising_right == c["increasing"] else "$x<0$")


def assert_vertex(c):
    """الرأس من التماثل: قيم متساوية على بعدين متساويين عن محور التماثل، وقيمة الرأس طرف لها."""
    h, k = c["vertex"]
    assert number(c["f"], h) == pytest.approx(float(k))
    sides = [number(c["f"], h + d) - k for d in (-3, -1, sp.Rational(1, 2), 1, 3)]
    assert sides[0] == pytest.approx(sides[4]) and sides[1] == pytest.approx(sides[3])
    assert all(v > 0 for v in sides) or all(v < 0 for v in sides)


def assert_vertex_point(c):
    assert_vertex(c)
    px, py = c["point"]
    assert number(c["f"], px) == pytest.approx(float(py))


def assert_translation(c):
    """موضع أصغر قيمة للدالة المزاحة يحدد اتجاهي الإزاحة ومقداريهما كما في النص."""
    values = {px: number(c["g"], px) for px in range(-10, 11)}
    h = min(values, key=values.__getitem__)
    k = round(values[h])
    for px in (-2, 0, 3):
        assert number(c["g"], px + h) - k == pytest.approx(px * px)
    text = c["text"]
    assert ("اليمين" in text) == (h > 0) and ("اليسار" in text) == (h < 0)
    assert ("الأعلى" in text) == (k > 0) and ("الأسفل" in text) == (k < 0)
    for size in (abs(h), abs(k)):
        assert {1: "وحدة واحدة", 2: "وحدتين"}.get(size, f"${size}$ وحدات") in text


def assert_table_rule(c):
    """كثيرة حدود الاستكمال عبر نقاط الجدول هي ax² (بلا حد خطي ولا ثابت)، وقيمتها عند النقطة المطلوبة."""
    poly = sp.expand(sp.interpolate(list(zip(c["xs"], c["values"])), x))
    a = poly.coeff(x, 2)
    assert sp.expand(poly - a * x**2) == 0 and a != 0
    assert c["answer"] == f"$a={sp.latex(a)}$، و$f({c['at']})={sp.latex(poly.subs(x, c['at']))}$"


def shift_words(steps):
    return {1: "وحدة واحدة", 2: "وحدتين"}.get(steps, f"${steps}$ وحدات")


def assert_vertical_shift(c):
    """الفرق g(x)−f(x) ثابت في كل النقاط وهو مقدار الإزاحة الرأسية، والرأس (0,k)."""
    diffs = {round(number(c["g"], px) - number(c["f"], px), 9) for px in (-3, -1, 0, 2, 5)}
    assert len(diffs) == 1
    k = int(diffs.pop())
    answer = c["answer"]
    assert ("الأعلى" in answer) == (k > 0) and ("الأسفل" in answer) == (k < 0)
    assert shift_words(abs(k)) in answer and f"$(0,{k})$" in answer


def assert_horizontal_shift(c):
    """المشتقة تنعدم عند h وحده، وg(h+d)=f(d) لكل d، فالإزاحة أفقية مقدارها |h| بلا إزاحة رأسية."""
    (h,) = sp.solve(sp.diff(c["g"], x), x)
    for d in (-2, 0, 1, 3):
        assert number(c["g"], h + d) == pytest.approx(number(c["f"], d))
    answer = c["answer"]
    assert ("اليمين" in answer) == (h > 0) and ("اليسار" in answer) == (h < 0)
    assert shift_words(abs(h)) in answer and f"$({h},0)$" in answer


def assert_mirror_point(c):
    """المقطع y ونظيره على ارتفاع واحد، ومنتصفهما على محور التماثل الذي تنعدم عنده المشتقة."""
    px, py = c["point"]
    axis = sp.solve(sp.diff(c["f"], x), x)
    assert px != 0 and axis == [sp.Rational(px, 2)]
    assert number(c["f"], 0) == pytest.approx(float(py)) and number(c["f"], px) == pytest.approx(float(py))
    assert f"$(0,{py})$" in c["answer"] and f"$({px},{py})$" in c["answer"]


def assert_standard_features(c):
    answer = c["answer"]
    assert f"هو ${round(number(c['f'], 0))}$" in answer
    assert ("الأعلى" in answer) == (number(c["f"], 1000) > 0)
    assert ("الأعلى" in answer) != ("الأسفل" in answer)


def assert_parabola_extreme(c):
    at, value = c["at"], float(c["value"])
    assert number(c["f"], at) == pytest.approx(value)
    sides = [number(c["f"], at + d) for d in (-2, -0.5, 0.5, 2)]
    is_max = all(v < value for v in sides)
    assert is_max or all(v > value for v in sides)
    assert c["answer"] == f"قيمة {'عظمى' if is_max else 'صغرى'} تساوي ${c['value']}$"


def assert_compare_maxima(c):
    """القيمة العظمى للدالة الأولى من قيمها على شبكة تمر بالرأس، ثم المقارنة بالثانية."""
    f = sp.lambdify(x, c["f"])
    top = max(f(v) for v in samples(c["low"], c["high"], 1201))
    name = "f" if top > c["other"] else "g"
    assert c["answer"] == f"الدالة ${name}$، والفرق ${round(abs(top - c['other']))}$"
    assert abs(top - c["other"]) >= 1


def real_roots(expr):
    """الجذور الحقيقية المختلفة بعزل الجذور الدقيق في sympy، لا بالطريقة التي بُنيت بها المعادلة."""
    return sorted(float(sp.N(root)) for root in set(sp.Poly(expr, x).real_roots()))


def assert_roots(c):
    want = sorted({float(sp.N(root)) for root in c["roots"]})
    got = real_roots(c["f"])
    assert len(got) == len(want) and got == pytest.approx(want, abs=TOL)


def assert_solution_count(c):
    """عدد الحلول من عزل الجذور، والمميز من الفرق بين الجذرين المركبين: a²(r₁-r₂)²."""
    assert len(real_roots(c["f"])) == c["count"]
    if "discriminant" in c:
        poly = sp.Poly(c["f"], x)
        first, second = poly.all_roots()
        value = complex(sp.N(poly.LC() ** 2 * (first - second) ** 2))
        assert value.real == pytest.approx(c["discriminant"]) and abs(value.imag) < TOL


def assert_sign_change(c):
    low, high = c["low"], c["high"]
    assert high == low + 1 and number(c["f"], low) * number(c["f"], high) < 0
    assert sum(low < root < high for root in real_roots(c["f"])) == 1


def assert_approx_root(c):
    """الحل الموجب الوحيد يُقرَّب إلى الجواب المكتوب بجزء من عشرة."""
    positive = [root for root in real_roots(c["f"]) if root > 0]
    assert len(positive) == 1 and abs(positive[0] - c["value"]) <= 0.05 + TOL


def assert_rectangle(c):
    assert c["width"] > 0 and c["length"] - c["width"] == c["extra"]
    assert c["width"] * c["length"] == c["area"]


def assert_factored_axis(c):
    assert_roots(c)
    for d in (1, 2.5):
        assert number(c["f"], c["axis"] + d) == pytest.approx(number(c["f"], c["axis"] - d))


def assert_factored_point(c):
    assert_roots(c)
    px, py = c["point"]
    assert number(c["f"], px) == pytest.approx(float(py))


def assert_radical(c):
    """قيمة المقدار الأصلي تساوي الصورة المبسطة عدديًا، والمجذور بلا عامل مربع كامل."""
    square, coefficient, radicand = (sp.sympify(c[key]) for key in ("square", "coefficient", "radicand"))
    for at in (2, 3):
        simplified = number(coefficient, at) * math.sqrt(number(radicand, at))
        assert math.sqrt(number(square, at)) == pytest.approx(simplified)
    free = int(radicand.subs(x, 1))
    assert free > 1 and all(free % (d * d) for d in range(2, math.isqrt(free) + 1))
    assert sp.degree(radicand, x) <= 1


def assert_perfect_square(c):
    """ثلاثية الحدود مربع كامل: تنعدم عند نصف معامل x بإشارة معكوسة، وتساوي مربع البعد عنه."""
    f, at = x**2 + c["b"] * x + c["c"], -sp.Rational(c["b"], 2)
    assert number(f, at) == pytest.approx(0, abs=TOL)
    assert number(f, at + 1) == pytest.approx(1) and number(f, at - 2) == pytest.approx(4)


def denominators(c):
    """جداء مقامات طرفي المعادلة النسبية كما كُتبت، قبل أي اختصار."""
    return sp.denom(sp.together(c["lhs"])) * sp.denom(sp.together(c["rhs"]))


def assert_rational_equation(c):
    """الحلول جذور بسط الفرق بين الطرفين بعد اختصاره؛ وغير المقبول يُعدِم مقامًا ويحقق المعادلة بلا مقامات."""
    numerator, _ = sp.fraction(sp.cancel(sp.together(c["lhs"] - c["rhs"])))
    want = sorted(float(value) for value in c["solutions"])
    assert real_roots(numerator) == pytest.approx(want, abs=TOL)
    for value in c["solutions"]:
        assert denominators(c).subs(x, value) != 0
        assert number(c["lhs"] - c["rhs"], value) == pytest.approx(0, abs=TOL)
    extraneous = c.get("extraneous", ())
    for value in extraneous:
        assert denominators(c).subs(x, value) == 0
    if "cleared" in c:
        every = sorted(float(value) for value in (*c["solutions"], *extraneous))
        assert real_roots(c["cleared"]) == pytest.approx(every, abs=TOL)


def assert_excluded_values(c):
    assert real_roots(denominators(c)) == pytest.approx(sorted(float(v) for v in c["values"]), abs=TOL)


def assert_work_rate(c):
    """مجموع معدّلي العمل المنفردين يساوي معدّل العمل معًا، والنسبة بين المدتين كما في النص."""
    first, second = c["times"]
    assert first > 0 and second > 0 and c["answer"] in c["times"]
    assert 1 / first + 1 / second == pytest.approx(1 / c["together"])
    if "ratio" in c:
        assert first == c["ratio"] * second


def assert_system(c):
    """حلول النظام من حلّال sympy لا من طريقة البناء: الأزواج الحقيقية المختلفة وعددها."""
    found = sorted(
        {
            (float(sp.N(px)), float(sp.N(py)))
            for px, py in sp.solve(c["equations"], [x, y])
            if sp.im(px) == 0 and sp.im(py) == 0
        }
    )
    if "count" in c:
        assert len(found) == c["count"]
    if "solutions" in c:
        want = sorted((float(px), float(py)) for px, py in c["solutions"])
        assert len(found) == len(want)
        for got, expected in zip(found, want, strict=True):
            assert got == pytest.approx(expected, abs=TOL)


COMPARE = {"<": operator.lt, ">": operator.gt, "<=": operator.le, ">=": operator.ge}


def horner(expr, at):
    value = Fraction(0)
    for coefficient in sp.Poly(expr, x).all_coeffs():
        value = value * at + Fraction(int(coefficient.p), int(coefficient.q))
    return value


def in_piece(at, piece):
    low, high, closed_low, closed_high = piece
    above = low is None or at > low or (closed_low and at == low)
    below = high is None or at < high or (closed_high and at == high)
    return above and below


def assert_inequality(c):
    """على شبكة كثيفة تضم الأطراف: الانتماء إلى الفترات المكتوبة يساوي تحقق الشروط كلها بحساب كسري تام."""
    for step in range(-60, 61):
        at = Fraction(step, 4)
        holds = all(COMPARE[op](horner(expr, at), 0) for expr, op in c["conditions"])
        assert holds == any(in_piece(at, piece) for piece in c["pieces"]), at


def assert_circle(c):
    """نقاط تبعد عن المركز طول نصف القطر تحقق المعادلة، والمركز لا يحققها، والنقاط المعطاة على الدائرة."""
    (h, k), length = c["center"], math.sqrt(c["radius2"])

    def value(px, py):
        return float(c["equation"].subs({x: px, y: py}))

    for degrees in range(0, 360, 40):
        angle = math.radians(degrees)
        assert value(h + length * math.cos(angle), k + length * math.sin(angle)) == pytest.approx(0, abs=TOL)
    assert value(h, k) == pytest.approx(-c["radius2"])
    given = c.get("points", ())
    for px, py in given:
        assert math.hypot(px - h, py - k) == pytest.approx(length)
    if c.get("diameter"):
        (x1, y1), (x2, y2) = given
        assert ((x1 + x2) / 2, (y1 + y2) / 2) == (h, k)
        assert math.dist((x1, y1), (x2, y2)) == pytest.approx(2 * length)


def assert_circle_position(c):
    (h, k), (px, py) = c["center"], c["point"]
    distance, length = math.hypot(px - h, py - k), math.sqrt(c["radius2"])
    if math.isclose(distance, length, abs_tol=TOL):
        assert c["position"] == "on"
    else:
        assert c["position"] == ("inside" if distance < length else "outside")


def exact(value):
    value = sp.nsimplify(value)
    return Fraction(int(value.p), int(value.q))


def side_lengths(a, b, c):
    return sorted((math.dist(a, b), math.dist(b, c), math.dist(c, a)))


def from_sas(first, second, degrees):
    """رؤوس مثلث من ضلعين وزاويتهما المحصورة."""
    angle = math.radians(degrees)
    return (0.0, 0.0), (first, 0.0), (second * math.cos(angle), second * math.sin(angle))


def from_sss(a, b, c):
    """رؤوس مثلث من أضلاعه الثلاثة، ويفشل إن خالفت متباينة المثلث."""
    assert a + b > c and b + c > a and a + c > b
    px = (a * a + c * c - b * b) / (2 * a)
    return (0.0, 0.0), (float(a), 0.0), (px, math.sqrt(c * c - px * px))


def from_asa(alpha, beta):
    """رؤوس مثلث من زاويتين وضلعهما المشترك بطول واحد."""
    gamma = 180 - alpha - beta
    assert gamma > 0
    side = math.sin(math.radians(beta)) / math.sin(math.radians(gamma))
    return (
        (0.0, 0.0),
        (1.0, 0.0),
        (side * math.cos(math.radians(alpha)), side * math.sin(math.radians(alpha))),
    )


def assert_same_shape(one, two):
    """مثلثان متشابهان: النسب بين أضلاعهما مرتّبةً متساوية."""
    ratios = [q / p for p, q in zip(side_lengths(*one), side_lengths(*two), strict=True)]
    assert ratios == pytest.approx([ratios[0]] * 3)


def assert_criterion(c):
    """المعطى من نوع المبرهنة المذكورة فعلًا، ويُنتج مثلثين متشابهين عند بنائهما هندسيًا."""
    first, second = c["first"], c["second"]
    if c["kind"] == "AA":
        assert "sides" not in first and sorted(first["angles"]) == sorted(second["angles"])
        assert_same_shape(from_asa(*first["angles"]), from_asa(*second["angles"]))
    elif c["kind"] == "SSS":
        assert "angles" not in first and "angle" not in first
        factors = {Fraction(q, p) for p, q in zip(first["sides"], second["sides"], strict=True)}
        assert len(factors) == 1
        assert_same_shape(from_sss(*first["sides"]), from_sss(*second["sides"]))
    else:
        assert "angles" not in first and len(first["sides"]) == 2
        (p, q), (big_p, big_q) = first["sides"], second["sides"]
        assert Fraction(big_p, p) == Fraction(big_q, q) and first["angle"] == second["angle"]
        assert_same_shape(from_sas(p, q, first["angle"]), from_sas(big_p, big_q, second["angle"]))


def assert_similar_sides(c):
    ratios = {exact(q) / exact(p) for p, q in zip(c["first"], c["second"], strict=True)}
    assert len(ratios) == 1
    if "perimeter" in c:
        assert exact(c["perimeter"][1]) / exact(c["perimeter"][0]) == ratios.pop()


def assert_similar_algebra(c):
    first, second, small, large = c["proportion"]
    assert sp.solve(first * large - second * small, x) == [c["x"]]
    assert second.subs(x, c["x"]) == c["value"] and first.subs(x, c["x"]) > 0 and c["value"] > 0


def assert_proportion(c):
    (h, s), (big_h, big_s) = c["pairs"]
    assert big_h == c["value"] and exact(h) / exact(s) == exact(big_h) / exact(big_s)
    assert math.atan2(h, s) == pytest.approx(math.atan2(big_h, big_s))


def right_triangle(first, second):
    """C عند الأصل وA وB على المحورين، وD أسفل العمود من C على الوتر؛ أطوال القطع من الإحداثيات."""
    a, b, origin = (first, 0.0), (0.0, second), (0.0, 0.0)
    along = ((origin[0] - a[0]) * (b[0] - a[0]) + (origin[1] - a[1]) * (b[1] - a[1])) / math.dist(a, b) ** 2
    d = (a[0] + along * (b[0] - a[0]), a[1] + along * (b[1] - a[1]))
    return a, b, origin, d


def assert_altitude(c):
    first, second = c["legs"]
    a, b, origin, d = right_triangle(first, second)
    measured = {
        "AC": first,
        "BC": second,
        "AB": math.dist(a, b),
        "AD": math.dist(a, d),
        "DB": math.dist(d, b),
        "CD": math.dist(origin, d),
    }
    assert measured[c["asked"]] == pytest.approx(float(c["value"]))
    for name, value in c.get("given", {}).items():
        assert measured[name] == pytest.approx(float(value))


def assert_similar_right_proportion(c):
    """أطوال الشكل من الإحداثيات: المعطى والمطلوب صحيحان، ونسب ACD وCBD متساوية (تشابه المثلثين)."""
    first, second = c["legs"]
    a, b, origin, d = right_triangle(first, second)
    measured = {
        "AC": first,
        "BC": second,
        "AD": math.dist(a, d),
        "DB": math.dist(d, b),
        "CD": math.dist(origin, d),
    }
    for name, value in c["given"].items():
        assert measured[name] == pytest.approx(float(value))
    assert measured[c["asked"]] == pytest.approx(float(c["value"]))
    ratio = measured["AC"] / measured["BC"]
    assert measured["AD"] / measured["CD"] == pytest.approx(ratio)
    assert measured["CD"] / measured["DB"] == pytest.approx(ratio)


def assert_geometric_mean(c):
    """مثلث قائم ساقاه من قطعتي الوتر: العمود النازل عليه يقسمه إلى القطعتين، وطوله هو الجواب."""
    first, second = c["parts"]
    legs = math.sqrt(first * (first + second)), math.sqrt(second * (first + second))
    a, b, origin, d = right_triangle(*legs)
    assert math.dist(a, d) == pytest.approx(first) and math.dist(d, b) == pytest.approx(second)
    assert math.dist(origin, d) == pytest.approx(float(c["value"]))


def assert_similarity_statement(c):
    """القائمة في الرأس الثالث، والترتيب المذكور يعطي نسبًا متساوية، وكل ترتيب خاطئ لا يعطيها."""
    first, second = c["legs"]
    a, b, origin, d = right_triangle(first, second)
    name_a, name_b, name_c, name_d = c["names"]
    points = {name_a: a, name_b: b, name_c: origin, name_d: d}
    base = (name_a, name_b, name_c)

    def ratios(order):
        return [
            math.dist(points[order[i]], points[order[(i + 1) % 3]])
            / math.dist(points[base[i]], points[base[(i + 1) % 3]])
            for i in range(3)
        ]

    right = ratios(c["answer"])
    assert right == pytest.approx([right[0]] * 3)
    for order in c["wrong"]:
        assert sorted(order) == sorted(c["answer"])
        assert ratios(order) != pytest.approx([ratios(order)[0]] * 3)


def triangle_with_parallel(ad, db, ae, ec, degrees=52):
    """مثلث ABC فيه D وE بالأطوال المعطاة؛ يرجع النقاط A وB وC وD وE."""
    a, b = (0.0, 0.0), (float(ad + db), 0.0)
    angle = math.radians(degrees)
    c = ((ae + ec) * math.cos(angle), (ae + ec) * math.sin(angle))
    d, e = (float(ad), 0.0), (ae * math.cos(angle), ae * math.sin(angle))
    return a, b, c, d, e


def cross(u, v):
    return u[0] * v[1] - u[1] * v[0]


def assert_de_parallel_to_bc(b, c, d, e):
    assert cross((e[0] - d[0], e[1] - d[1]), (c[0] - b[0], c[1] - b[1])) == pytest.approx(0, abs=1e-9)


def assert_parallel_division(c):
    """نبني المثلث بالأطوال الأربعة (منها الجواب)؛ يصح الجواب فقط إن وازى DE القطعة BC."""
    values = {**c["values"], "AC": c["values"]["AE"] + c["values"]["EC"]}
    assert values[c["asked"]] == c["value"]
    _, b, cc, d, e = triangle_with_parallel(*(values[n] for n in ("AD", "DB", "AE", "EC")))
    assert_de_parallel_to_bc(b, cc, d, e)


def assert_midsegment(c):
    """D وE منتصفا ضلعين في مثلث عام: DE يوازي BC وطوله نصفه."""
    a, b, cc = (0.0, 0.0), (7.0, 1.0), (2.0, 5.0)
    factor = c["base"] / math.dist(b, cc)
    a, b, cc = (tuple(factor * v for v in p) for p in (a, b, cc))
    d, e = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), ((a[0] + cc[0]) / 2, (a[1] + cc[1]) / 2)
    assert_de_parallel_to_bc(b, cc, d, e)
    assert math.dist(d, e) == pytest.approx(c["mid"])
    assert (c["mid"] if c["asked"] == "DE" else c["base"]) == c["value"]


def assert_medial_perimeter(c):
    a, b, cc = from_sss(*c["sides"])
    mids = [((p[0] + q[0]) / 2, (p[1] + q[1]) / 2) for p, q in ((a, b), (b, cc), (cc, a))]
    perimeter = sum(math.dist(mids[i], mids[(i + 1) % 3]) for i in range(3))
    assert perimeter == pytest.approx(c["value"])


def assert_parallel_algebra(c):
    """المعادلة الناتجة من التناسب لها حلّ وحيد هو x، وبالأطوال الناتجة يوازي DE القطعة BC."""
    ad, db, ae, ec = c["proportion"]
    assert sp.solve(ad * ec - db * ae, x) == [c["x"]]
    at = [sp.sympify(value).subs(x, c["x"]) for value in (ad, db, ae, ec)]
    assert min(at) > 0 and at[0] + at[1] == c["total"]
    _, b, cc, d, e = triangle_with_parallel(*(float(value) for value in at))
    assert_de_parallel_to_bc(b, cc, d, e)


def assert_transversals(c):
    """ثلاثة مستقيمات أفقية بمسافتين متناسبتين مع القطعتين الأوليين؛ القاطع الثاني يقطعها بالنسبة نفسها."""
    p, q = c["first"]
    heights = (p / (p + q), q / (p + q))
    parts = tuple(height * c["total"] for height in heights)
    assert parts == pytest.approx(c["second"]) and sum(c["second"]) == c["total"]


def assert_table_limit(c):
    """غير معرفة عند النقطة (المقام صفر)، وقيم الجهتين القريبة تقترب من النهاية."""
    assert c["bottom"].subs(x, c["at"]) == 0
    f = c["top"] / c["bottom"]
    for h in (sp.Rational(1, 10**4), sp.Rational(-1, 10**4)):
        assert number(f, c["at"] + h) == pytest.approx(float(c["value"]), abs=1e-3)


def side_values(expr, at, side):
    h = sp.Rational(1, 10**6)
    return {
        "-": [number(expr, at - h)],
        "+": [number(expr, at + h)],
        "both": [number(expr, at - h), number(expr, at + h)],
    }[side]


def assert_infinite_side(c):
    """قيم قريبة جدًا من النقطة تكبر بلا حد، وإشاراتها تعيّن +∞ أو −∞ أو عدم الوجود."""
    values = side_values(c["expr"], c["at"], c["side"])
    assert all(abs(v) > 1e5 for v in values)
    signs = {1 if v > 0 else -1 for v in values}
    expected = NO_LIMIT if len(signs) == 2 else (r"$+\infty$" if signs == {1} else r"$-\infty$")
    assert c["answer"] == expected


def assert_removable(c):
    """النهاية عند النقطة القابلة للإزالة تساوي القيمة، والقطب الآخر لانهائي."""
    assert_limit({"expr": c["expr"], "at": c["at"], "value": c["value"]})
    assert all(abs(v) > 1e5 for v in side_values(c["expr"], c["pole"], "both"))


def assert_discontinuities(c):
    """الأصفار الحقيقية للمقام عدديًا هي النقاط المذكورة، والبسط معرف ومتصل عندها."""
    roots = sorted(float(r) for r in sp.Poly(c["bottom"], x).nroots() if abs(sp.im(r)) < 1e-12)
    assert roots == pytest.approx(sorted(c["points"]))
    assert all(math.isfinite(number(c["top"], p)) for p in c["points"])


def assert_implicit_second(c):
    """y عدديًا من العلاقة قرب النقطة ثم فرق مركزي ثانٍ، مستقل عن الاشتقاق الضمني."""
    F = sp.lambdify((x, y), c["F"], "mpmath")
    mpmath.mp.dps = 40
    p, q = c["point"]
    assert c["F"].subs({x: p, y: q}) == 0
    h = mpmath.mpf(10) ** -6
    near = [mpmath.findroot(lambda v, s=s: F(p + s, v), q) for s in (h, 0, -h)]
    second = (near[0] - 2 * near[1] + near[2]) / h**2
    assert float(second) == pytest.approx(float(c["value"]), abs=1e-4)


CHECKS = {
    "rational_equation": assert_rational_equation,
    "excluded_values": assert_excluded_values,
    "work_rate": assert_work_rate,
    "system": assert_system,
    "inequality": assert_inequality,
    "circle": assert_circle,
    "circle_position": assert_circle_position,
    "criterion": assert_criterion,
    "similar_sides": assert_similar_sides,
    "similar_algebra": assert_similar_algebra,
    "proportion": assert_proportion,
    "altitude": assert_altitude,
    "geometric_mean": assert_geometric_mean,
    "similar_right_proportion": assert_similar_right_proportion,
    "similarity_statement": assert_similarity_statement,
    "parallel_division": assert_parallel_division,
    "midsegment": assert_midsegment,
    "medial_perimeter": assert_medial_perimeter,
    "parallel_algebra": assert_parallel_algebra,
    "transversals": assert_transversals,
    "roots": assert_roots,
    "solution_count": assert_solution_count,
    "sign_change": assert_sign_change,
    "approx_root": assert_approx_root,
    "rectangle": assert_rectangle,
    "factored_axis": assert_factored_axis,
    "factored_point": assert_factored_point,
    "radical": assert_radical,
    "perfect_square": assert_perfect_square,
    "value": assert_value,
    "parabola_shape": assert_parabola_shape,
    "parabola_monotone": assert_parabola_monotone,
    "vertex": assert_vertex,
    "vertex_point": assert_vertex_point,
    "translation": assert_translation,
    "table_rule": assert_table_rule,
    "vertical_shift": assert_vertical_shift,
    "horizontal_shift": assert_horizontal_shift,
    "mirror_point": assert_mirror_point,
    "standard_features": assert_standard_features,
    "parabola_extreme": assert_parabola_extreme,
    "compare_maxima": assert_compare_maxima,
    "shape_signs": assert_shape_signs,
    "second_derivative_test": assert_second_derivative_test,
    "sketch_summary": assert_sketch_summary,
    "graph_shape": assert_graph_shape,
    "continuity_bool": assert_continuity_bool,
    "continuity2": assert_continuity2,
    "differentiable": assert_differentiable,
    "avg_instant": assert_avg_instant,
    "tangent": assert_tangent,
    "zeros": assert_zeros,
    "implicit_expr": assert_implicit_expr,
    "graph_limit": assert_graph_limit,
    "graph_discontinuity": assert_graph_discontinuity,
    "graph_tangent": assert_graph_tangent,
    "graph_sign": assert_graph_sign,
    "graph_extremum": assert_graph_extremum,
    "graph_concavity": assert_graph_concavity,
    "graph_options": assert_graph_options,
    "limit": assert_limit,
    "derivative": assert_derivative,
    "function": assert_function,
    "implicit": assert_implicit,
    "monotonic": assert_monotonic,
    "local": assert_local,
    "absolute": assert_absolute,
    "inflection": assert_inflection,
    "concavity": assert_concavity,
    "optimum": assert_optimum,
    "turning": assert_turning,
    "surface": assert_surface,
    "one_sided": assert_one_sided,
    "continuity": assert_continuity,
    "average": assert_average,
    "table_limit": assert_table_limit,
    "infinite_side": assert_infinite_side,
    "removable": assert_removable,
    "discontinuities": assert_discontinuities,
    "implicit_second": assert_implicit_second,
}


@pytest.mark.parametrize(("lesson", "generator"), ALL, ids=IDS)
def test_answers_are_correct(lesson, generator):
    for seed in SEEDS:
        problem = generator(random.Random(seed))
        CHECKS[problem.check["type"]](problem.check)


@pytest.mark.parametrize(("lesson", "generator"), ALL, ids=IDS)
def test_problem_shape(lesson, generator):
    for seed in SEEDS:
        problem = generator(random.Random(seed))
        text = " ".join([problem.stem, problem.answer, *problem.wrong, *problem.steps])
        assert problem.lesson == lesson
        assert problem.level in {"K", "A", "R"}
        assert problem.steps
        assert text.count("$") % 2 == 0, text
        assert not any(bad in text for bad in ("zoo", "nan", "None"))
        if problem.mcq_ok:
            assert len(set(problem.wrong)) == 3, (seed, problem.answer, problem.wrong)
            assert problem.answer not in problem.wrong
        if problem.graph is not None:
            assert_graph_in_window(problem.graph)
        for option in problem.option_graphs:
            assert_graph_in_window(option)
        assert problem.mcq_ok or problem.essay_ok


def assert_graph_in_window(graph):
    x_min, x_max, y_min, y_max = graph["window"]
    margin = (y_max - y_min) * 0.021
    assert graph["curves"], "رسم بلا منحنى"
    for curve in graph["curves"]:
        for px, py in curve:
            assert x_min <= px <= x_max and y_min - margin <= py <= y_max + margin
    for px, py, _ in graph["dots"]:
        assert x_min <= px <= x_max and y_min <= py <= y_max


def test_every_lesson_has_easy_and_higher_order_variants():
    from apps.papers.domain.generators import lesson_levels

    for lesson in available_lessons():
        levels = set(lesson_levels(lesson)) | set(lesson_levels(lesson, "mcq"))
        assert {"K", "A", "R"} <= levels, (lesson, levels)


def test_every_tested_lesson_has_a_generator():
    tested = "1.1 1.2 1.3 1.4 2.1 2.2 2.3 2.4 2.5 2.6 2.7 2.8 2.9 3.1 3.2 3.3 3.4 3.5"
    assert available_lessons() == set(tested.split())


def test_twenty_question_worksheet_for_every_lesson_and_level():
    """ورقة عمل من 20 مسألة بلا تكرار ممكنة لكل درس وكل مستوى متاح."""
    from apps.papers.domain.generators import generate, lesson_levels

    for lesson in available_lessons():
        for level in lesson_levels(lesson):
            rng, used = random.Random(0), set()
            for _ in range(20):
                used.add(generate(lesson, rng, "essay", used, level).key)
            assert len(used) == 20, (lesson, level)
