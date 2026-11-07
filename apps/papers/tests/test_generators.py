"""كل جواب يُتحقق منه عدديًا بطريقة مستقلة عن طريقة بنائه، عبر بذور كثيرة."""

import random

import mpmath
import pytest
import sympy as sp

from apps.papers.domain.generators import NO_LIMIT, REGISTRY, available_lessons, x, y
from apps.papers.domain.graphs import value_at

SEEDS = range(120)
ALL = [(lesson, fn) for lesson, fns in REGISTRY.items() for fn in fns]
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


CHECKS = {
    "graph_limit": assert_graph_limit,
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


def assert_graph_in_window(graph):
    x_min, x_max, y_min, y_max = graph["window"]
    margin = (y_max - y_min) * 0.021
    assert graph["curves"], "رسم بلا منحنى"
    for curve in graph["curves"]:
        for px, py in curve:
            assert x_min <= px <= x_max and y_min - margin <= py <= y_max + margin
    for px, py, _ in graph["dots"]:
        assert x_min <= px <= x_max and y_min <= py <= y_max


def test_every_tested_lesson_has_a_generator():
    tested = "1.1 1.2 1.3 1.4 2.1 2.2 2.3 2.4 2.5 2.6 2.7 2.8 2.9 3.1 3.2 3.3 3.5"
    assert available_lessons() == set(tested.split())
