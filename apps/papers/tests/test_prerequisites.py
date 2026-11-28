import random

import pytest
import sympy as sp

from apps.papers.domain.prerequisites import PREREQUISITES

ALL = [fn for fns in PREREQUISITES.values() for fn in fns]


def _expected(check):
    """حساب مستقل عن المولّد من معطيات المسألة وحدها."""
    x = sp.Symbol("x")
    if check["type"] == "linear_root":
        return sp.solve(check["a"] * x + check["b"] - check["c"], x)[0]
    if check["type"] == "value_at":
        a, b, c = check["coefficients"]
        return (a * x**2 + b * x + c).subs(x, check["at"])
    (x1, y1), (x2, y2) = check["points"]
    return sp.Line(sp.Point(x1, y1), sp.Point(x2, y2)).slope


@pytest.mark.parametrize("fn", ALL, ids=lambda fn: fn.__name__)
def test_prerequisite_answer_is_independently_correct(fn):
    for seed in range(200):
        problem = fn(random.Random(seed))
        assert problem.answer == f"${sp.latex(_expected(problem.check))}$", seed
        assert len({problem.answer, *problem.wrong}) == 4, seed
        assert len(problem.wrong_kinds) == 3
