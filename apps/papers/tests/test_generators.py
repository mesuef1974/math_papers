"""كل جواب يُتحقق منه عدديًا بطريقة مستقلة عن طريقة بنائه، عبر بذور كثيرة."""

import random

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


CHECKS = {
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
