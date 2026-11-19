"""أسئلة تُقرأ من تمثيل بياني، على أنماط الكتاب والاختبارات: عدم الاتصال، وميل المماس، وقراءة f′.

كل رسم يُبنى من دالة معاملاتها صحيحة أو أنصاف، فتقع النقاط المهمة على خطوط الشبكة ويمكن قراءتها.
الحقل check يحمل الرسم نفسه، فالاختبار يقرأ الجواب من النقاط المرسومة لا من معادلة البناء.
"""

from __future__ import annotations

import random

import sympy as sp

from .generators import Problem, m, variant, wrongs, x
from .graphs import Graph, Window

WINDOW = Window(-5, 5, -5, 5)
DERIV = "f′"
NONE_FOUND = "لا توجد"
TYPES = {"removable": "قابل للإزالة", "jump": "قفزي", "infinite": "لانهائي"}
CONTINUOUS = "الدالة متصلة عندها"


def interval_text(low: int | None, high: int | None) -> str:
    left = r"-\infty" if low is None else str(low)
    right = r"\infty" if high is None else str(high)
    return f"$({left},{right})$"


def union_outside(p: int, q: int) -> str:
    return rf"$(-\infty,{p})\cup({q},\infty)$"


@variant("1.4", example=1)
def discontinuity_type_from_graph(rng: random.Random) -> Problem:
    c = rng.randint(-2, 2)
    kind = rng.choice(list(TYPES))
    graph = Graph(WINDOW)
    if kind == "infinite":
        k = rng.choice([-2, -1, 1, 2])
        base = rng.randint(-1, 1)
        graph.add_curve(k / (x - c) + base, -5, c - 0.02).add_curve(
            k / (x - c) + base, c + 0.02, 5
        ).add_asymptote(c)
        reason = f"المنحنى يتجه إلى $\\pm\\infty$ قرب $x={c}$ ويوجد خط تقارب رأسي."
        check = {"left": None, "right": None}
    elif kind == "jump":
        low = rng.randint(-3, 2)
        high = low + rng.randint(1, 3)
        left_value, right_value = (low, high) if rng.random() < 0.5 else (high, low)
        graph.add_curve(left_value + rng.choice([-1, 1]) * sp.Rational(1, 2) * (x - c), -5, c)
        graph.add_curve(right_value + rng.choice([-1, 1]) * sp.Rational(1, 2) * (x - c), c, 5)
        graph.add_dot(c, left_value, closed=rng.random() < 0.5).add_dot(c, right_value, closed=False)
        reason = f"النهاية من اليسار ${left_value}$ ومن اليمين ${right_value}$، وهما مختلفتان."
        check = {"left": left_value, "right": right_value}
    else:
        value = rng.randint(-3, 3)
        curve = (
            value
            + rng.choice([-1, 1]) * sp.Rational(rng.choice([1, 2]), 4) * (x - c) ** 2
            + rng.choice([-1, 0, 1]) * (x - c)
        )
        graph.add_curve(curve, -5, 5).add_dot(c, value, closed=False)
        if rng.random() < 0.6:
            graph.add_dot(
                c, rng.choice([v for v in range(-4, 5) if v != value and (c, v) != (0, 0)]), closed=True
            )
        reason = f"النهاية موجودة وتساوي ${value}$، لكن قيمة الدالة عند ${c}$ لا تساويها أو غير معرفة."
        check = {"left": value, "right": value}
    answer = TYPES[kind]
    return Problem(
        "1.4",
        f"يبيّن الشكل التمثيل البياني للدالة $f$. ما نوع عدم الاتصال عند $x={c}$؟",
        answer,
        wrongs(answer, *[t for t in TYPES.values() if t != answer], CONTINUOUS),
        (reason, f"إذن عدم الاتصال {answer}."),
        "A",
        {"type": "graph_discontinuity", "graph": graph.as_dict(), "at": c, "kind": kind, **check},
        graph=graph.as_dict(),
    )


@variant("2.1", example=5)
def tangent_slope_from_graph(rng: random.Random) -> Problem:
    a, b = rng.randint(-2, 2), rng.randint(-2, 2)
    slope = rng.choice([-3, -2, -1, 1, 2, 3])
    bend = rng.choice([-1, 1]) * sp.Rational(rng.choice([1, 2]), 2)
    f = bend * (x - a) ** 2 + slope * (x - a) + b
    graph = Graph(WINDOW).add_curve(f, -5, 5).add_line(slope, (a, b)).add_dot(a, b, closed=True)
    pool = [m(b), m(-slope), m(slope + 1), m(slope - 1), m(a)]
    if abs(slope) > 1:
        pool.insert(0, m(sp.Rational(1, slope)))
    return Problem(
        "2.1",
        f"يبيّن الشكل منحنى الدالة $f$ والمماس المتقطع له عند النقطة $({a},{b})$. أوجد $f'({a})$.",
        m(slope),
        wrongs(m(slope), *pool),
        (
            f"المماس يمر بالنقطتين $({a},{b})$ و$({a + 1},{b + slope})$.",
            f"ميله $\\dfrac{{{b + slope}-({b})}}{{{a + 1}-({a})}}={slope}$، وميل المماس هو $f'({a})$.",
        ),
        "A",
        {"type": "graph_tangent", "graph": graph.as_dict(), "at": a, "y": b, "value": slope},
        graph=graph.as_dict(),
    )


def derivative_graph(rng: random.Random, double_root: bool = False) -> tuple[Graph, sp.Expr, int, int, int]:
    """تمثيل f′ له جذران صحيحان p<q (أو جذر مضاعف عند p). الإشارة s تحدد الاتجاه."""
    p = rng.randint(-3, 1)
    q = p + rng.choice([2, 3])
    s = rng.choice([-1, 1])
    if double_root:
        fprime = s * sp.Rational(1, 4) * (x - p) ** 2 * (x - q)
    else:
        fprime = s * sp.Rational(rng.choice([1, 2]), 2) * (x - p) * (x - q)
    return Graph(WINDOW, label=DERIV).add_curve(fprime, -5, 5), fprime, p, q, s


@variant("3.1", example=2)
def monotonic_from_derivative_graph(rng: random.Random) -> Problem:
    graph, _, p, q, s = derivative_graph(rng)
    ask_increasing = rng.choice([True, False])
    inner_positive = s < 0
    middle, outer = interval_text(p, q), union_outside(p, q)
    answer = middle if ask_increasing == inner_positive else outer
    word = "تزايد" if ask_increasing else "تناقص"
    sign_word = "موجبة (فوق المحور x)" if ask_increasing else "سالبة (تحت المحور x)"
    return Problem(
        "3.1",
        f"يبيّن الشكل التمثيل البياني للمشتقة $f'$. حدد فترات {word} الدالة $f$.",
        answer,
        wrongs(answer, middle, outer, interval_text(None, q), interval_text(p, None), interval_text(None, p)),
        (
            f"$f'$ تقطع المحور x عند $x={p}$ و$x={q}$.",
            f"$f$ {'متزايدة' if ask_increasing else 'متناقصة'} حيث تكون $f'$ {sign_word}: {answer}",
        ),
        "A",
        {
            "type": "graph_sign",
            "graph": graph.as_dict(),
            "p": p,
            "q": q,
            "positive": ask_increasing,
            "answer_inner": answer == middle,
        },
        graph=graph.as_dict(),
    )


@variant("3.2", example=2)
def extremum_from_derivative_graph(rng: random.Random) -> Problem:
    double = rng.random() < 0.35
    graph, _, p, q, s = derivative_graph(rng, double_root=double)
    want_max = rng.choice([True, False])
    if double:
        # جذر مضاعف عند p: لا تغيّر إشارة هناك، والتغيّر عند q فقط.
        changes = {q: "min" if s > 0 else "max"}
    else:
        changes = {p: "max", q: "min"} if s > 0 else {p: "min", q: "max"}
    found = [r for r, kind in changes.items() if kind == ("max" if want_max else "min")]
    answer = f"$x={found[0]}$" if found else NONE_FOUND
    word = "عظمى" if want_max else "صغرى"
    pool = [f"$x={p}$", f"$x={q}$", NONE_FOUND, f"$x={p - 1}$", f"$x={q + 1}$"]
    steps = [f"$f'$ تساوي صفرًا عند $x={p}$ و$x={q}$."]
    if double:
        steps.append(f"عند $x={p}$ تمس $f'$ المحور دون أن تغيّر إشارتها، فلا قيمة قصوى هناك.")
    steps.append(
        f"القيمة العظمى المحلية حيث تتغير $f'$ من موجبة إلى سالبة، والصغرى حيث تتغير من سالبة إلى موجبة: {answer}"
    )
    return Problem(
        "3.2",
        f"يبيّن الشكل التمثيل البياني للمشتقة $f'$. عند أي قيمة لـ $x$ يكون للدالة $f$ قيمة {word} محلية؟",
        answer,
        wrongs(answer, *pool),
        tuple(steps),
        "R",
        {"type": "graph_extremum", "graph": graph.as_dict(), "max": want_max, "answer": answer},
        graph=graph.as_dict(),
    )


@variant("3.3", example=3)
def concavity_from_derivative_graph(rng: random.Random) -> Problem:
    h = rng.randint(-2, 2)
    r = rng.choice([1, 2])
    s = rng.choice([-1, 1])
    a = sp.Rational(1, 2) if r == 2 else 1
    fprime = s * a * ((x - h) ** 2 - r**2)
    graph = Graph(WINDOW, label=DERIV).add_curve(fprime, -5, 5)
    ask = rng.choice(["up", "down", "inflection"])
    increasing_right = s > 0
    if ask == "inflection":
        answer = f"$x={h}$"
        question = "ما الإحداثي x لنقطة انعطاف منحنى الدالة $f$؟"
        pool = [f"$x={h - r}$", f"$x={h + r}$", f"$x={h + 1}$", NONE_FOUND]
    else:
        up = ask == "up"
        answer = interval_text(h, None) if up == increasing_right else interval_text(None, h)
        question = f"حدد الفترة التي يكون فيها منحنى الدالة $f$ مقعرًا إلى {'أعلى' if up else 'أسفل'}."
        pool = [
            interval_text(h, None),
            interval_text(None, h),
            interval_text(h - r, h + r),
            union_outside(h - r, h + r),
        ]
    return Problem(
        "3.3",
        f"يبيّن الشكل التمثيل البياني للمشتقة $f'$. {question}",
        answer,
        wrongs(answer, *pool),
        (
            "منحنى $f$ مقعر إلى أعلى حيث $f'$ متزايدة، وإلى أسفل حيث $f'$ متناقصة.",
            f"$f'$ تغيّر اتجاهها عند رأسها $x={h}$، فهناك نقطة الانعطاف.",
            f"الجواب: {answer}",
        ),
        "R",
        {"type": "graph_concavity", "graph": graph.as_dict(), "h": h, "ask": ask, "answer": answer},
        graph=graph.as_dict(),
    )


@variant("3.1", example=2)
def function_from_derivative_graph(rng: random.Random) -> Problem:
    """خيار من أربعة رسوم للدالة f: الصحيح، ومعكوسه، ومزاح أفقيًا، ورسم f′ نفسه."""
    graph, fprime, p, q, _ = derivative_graph(rng)
    antiderivative = sp.integrate(fprime, x)
    center = (antiderivative.subs(x, p) + antiderivative.subs(x, q)) / 2
    f = antiderivative - center
    shift = rng.choice([-1, 1])
    options = [
        Graph(WINDOW).add_curve(f, -5, 5),
        Graph(WINDOW).add_curve(-f, -5, 5),
        Graph(WINDOW).add_curve(f.subs(x, x - shift), -5, 5),
        Graph(WINDOW).add_curve(fprime, -5, 5),
    ]
    return Problem(
        "3.1",
        "يبيّن الشكل التمثيل البياني للمشتقة $f'$. أي التمثيلات البيانية الآتية يمكن أن يكون للدالة $f$؟",
        "graph:0",
        ("graph:1", "graph:2", "graph:3"),
        (
            "$f'>0$ حيث المنحنى فوق المحور x، فتكون $f$ متزايدة هناك، و$f'<0$ حيث تحته فتكون متناقصة.",
            f"إذن لـ $f$ قيمتان قصويان عند $x={p}$ و$x={q}$ بالترتيب الذي تحدده إشارة $f'$.",
        ),
        "R",
        {
            "type": "graph_options",
            "graph": graph.as_dict(),
            "options": [g.as_dict() for g in options],
            "p": p,
            "q": q,
        },
        graph=graph.as_dict(),
        option_graphs=tuple(g.as_dict() for g in options),
        essay_ok=False,
    )
