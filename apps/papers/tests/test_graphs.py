import pytest
import sympy as sp

from apps.papers.domain.graphs import Graph, Window, value_at

x = sp.Symbol("x", real=True)


def test_window_must_contain_origin():
    with pytest.raises(ValueError):
        Window(1, 5, -5, 5)


def test_curve_is_split_where_it_leaves_the_window():
    graph = Graph(Window(-5, 5, -5, 5)).add_curve(x**2 - 3, -5, 5)
    assert len(graph.curves) == 1  # يخرج من الأعلى عند الطرفين فيُقص دون أن ينقسم
    split = Graph(Window(-5, 5, -5, 5)).add_curve(1 / x, -5, 5)
    assert len(split.curves) == 2  # خط التقارب x=0 يقسم المنحنى
    for curve in split.curves:
        assert all(-5.2 <= py <= 5.2 for _, py in curve)


def test_value_at_reads_the_drawn_curve():
    graph = Graph(Window(-5, 5, -5, 5)).add_curve(2 * x - 1, -2, 3).as_dict()
    assert value_at(graph, 1.0)[0] == pytest.approx(1.0, abs=1e-3)
    assert value_at(graph, 4.0) == []


def test_dots_outside_window_are_rejected():
    with pytest.raises(ValueError):
        Graph(Window(-5, 5, -5, 5)).add_dot(6, 0)


def test_serialized_graph_is_plain_numbers():
    data = (
        Graph(Window(-4, 4, -3, 3), label="f′")
        .add_curve(x, -4, 4)
        .add_dot(0, 0, closed=False)
        .add_line(1, (0, 0))
        .as_dict()
    )
    assert data["window"] == [-4, 4, -3, 3]
    assert data["dots"] == [[0.0, 0.0, False]]
    assert data["label"] == "f′"
    assert all(isinstance(v, float) for curve in data["curves"] for point in curve for v in point)
