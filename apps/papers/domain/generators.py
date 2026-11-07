"""مولّدات مسائل أصلية بالمعاملات، بلا نص من أي كتاب. وحدة نقية لا تعرف Django.

كل مولّد يبني المسألة عكسيًا من حلها حتى تخرج الأرقام نظيفة. النص يحمل الرياضيات بين علامتي $.
الحقل check يصف المسألة لاختبار مستقل يتحقق من الجواب عدديًا، لا بالطريقة التي بُني بها.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from typing import Any

import sympy as sp

from .graphs import Graph, Window

x = sp.Symbol("x", real=True)
y = sp.Symbol("y", real=True)
NO_LIMIT = "غير موجودة"
MAX_ATTEMPTS = 60
LEVEL_NAMES = {"K": "سهل", "A": "متوسط", "R": "مهارات عليا"}
LEVEL_SAMPLES = 6  # بذور يُستدل بها على مستوى الصيغة ونوع السؤال الذي تصلح له
DYDX = r"\dfrac{dy}{dx}"


@dataclass(frozen=True)
class Problem:
    lesson: str
    stem: str
    answer: str
    wrong: tuple[str, ...]
    steps: tuple[str, ...]
    level: str  # K معرفة، A تطبيق، R استدلال
    check: dict[str, Any] = field(default_factory=dict, compare=False)
    mcq_ok: bool = True
    graph: dict[str, Any] | None = field(default=None, compare=False)  # وصف رسم من graphs.Graph
    option_graphs: tuple[dict[str, Any], ...] = field(
        default=(), compare=False
    )  # خيارات رسوم، الأول هو الصحيح
    essay_ok: bool = True

    @property
    def key(self) -> str:
        """هوية المسألة لمنع التكرار في الورقة: النص، ومعه الرسم لأن أسئلة الرسوم تتشابه نصًا."""
        return (
            self.stem
            if self.graph is None
            else f"{self.stem}|{self.graph['curves'][:1]}|{self.graph['dots']}"
        )


Generator = Callable[[random.Random], Problem]
REGISTRY: dict[str, list[Generator]] = {}


def variant(lesson: str) -> Callable[[Generator], Generator]:
    def register(fn: Generator) -> Generator:
        REGISTRY.setdefault(lesson, []).append(fn)
        return fn

    return register


class LevelUnavailableError(LookupError):
    """لا توجد صيغة للدرس بهذا المستوى ونوع السؤال."""


def available_lessons() -> set[str]:
    return set(REGISTRY)


@cache
def variant_profile(fn: Generator) -> tuple[frozenset[str], bool, bool]:
    """(المستويات، يصلح للموضوعي، يصلح للمقالي) لصيغة واحدة، من عينات ثابتة."""
    samples = [fn(random.Random(seed)) for seed in range(LEVEL_SAMPLES)]  # noqa: S311 — عينات ثابتة لا أمنية
    return (
        frozenset(p.level for p in samples),
        all(p.mcq_ok for p in samples),
        all(p.essay_ok for p in samples),
    )


def variants(lesson: str, kind: str = "essay", level: str | None = None) -> list[Generator]:
    pool = []
    for fn in REGISTRY.get(lesson, []):
        levels, mcq_ok, essay_ok = variant_profile(fn)
        if (mcq_ok if kind == "mcq" else essay_ok) and (level is None or level in levels):
            pool.append(fn)
    return pool


def lesson_levels(lesson: str, kind: str = "essay") -> list[str]:
    found: set[str] = set()
    for fn in variants(lesson, kind):
        found |= variant_profile(fn)[0]
    return [level for level in LEVEL_NAMES if level in found]


def generate(
    lesson: str,
    rng: random.Random,
    kind: str = "essay",
    avoid: set[str] | None = None,
    level: str | None = None,
) -> Problem:
    """يختار صيغة من مولّدات الدرس بالمستوى المطلوب إن حُدد، ويتفادى ما ظهر في الورقة نفسها."""
    avoid = avoid if avoid is not None else set()
    pool = variants(lesson, kind, level)
    if not pool:
        raise LevelUnavailableError(f"{lesson}/{kind}/{level}")
    for _ in range(MAX_ATTEMPTS):
        problem = rng.choice(pool)(rng)
        fits = problem.mcq_ok if kind == "mcq" else problem.essay_ok
        if fits and problem.key not in avoid and (level is None or problem.level == level):
            return problem
    raise ValueError(f"تعذر توليد مسألة جديدة للدرس {lesson}")


def tex(value: Any) -> str:
    return value if isinstance(value, str) else sp.latex(value, ln_notation=True)


def m(value: Any) -> str:
    return f"${tex(value)}$"


def nz(rng: random.Random, low: int, high: int) -> int:
    return rng.choice([n for n in range(low, high + 1) if n != 0])


def wrongs(answer: Any, *candidates: Any) -> tuple[str, ...]:
    """ثلاثة بدائل مختلفة: الأخطاء الشائعة أولًا، ثم قيم قريبة عند الحاجة."""
    shown = answer if isinstance(answer, str) else m(answer)
    pool = [*candidates]
    if not isinstance(answer, str):
        pool += [answer + 1, answer - 1, answer + 2, -answer, 2 * answer]
    seen = {shown}
    result: list[str] = []
    for candidate in pool:
        text = candidate if isinstance(candidate, str) else m(candidate)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result[:3])


def cases(*rows: tuple[Any, str]) -> str:
    body = r" \\ ".join(f"{tex(value)} & {condition}" for value, condition in rows)
    return rf"f(x)=\begin{{cases}} {body} \end{{cases}}"


def lim(at: Any, body: str) -> str:
    return rf"\lim_{{x \to {tex(at)}}} {body}"


def frac(top: Any, bottom: Any) -> str:
    return rf"\dfrac{{{tex(top)}}}{{{tex(bottom)}}}"


def minus(left: int, right: int) -> str:
    return f"{left}-{right}" if right >= 0 else f"{left}-({right})"


def cubic_with_critical_points(rng: random.Random) -> tuple[sp.Expr, int, int, int]:
    """دالة مشتقتها s·3(x-p)(x-q) حيث p<q، فالنقطتان الحرجتان صحيحتان بالبناء."""
    p = rng.randint(-3, 2)
    q = p + rng.choice([2, 4])
    sign = rng.choice([1, 1, -1])
    constant = rng.randint(-4, 6)
    f = sign * (x**3 - sp.Rational(3 * (p + q), 2) * x**2 + 3 * p * q * x) + constant
    return f, p, q, sign


# الوحدة الأولى: النهايات والاتصال
@variant("1.1")
def limit_from_piecewise(rng: random.Random) -> Problem:
    c, value = rng.randint(-3, 4), rng.randint(-5, 8)
    a = nz(rng, -3, 4)
    d = rng.choice([n for n in range(-3, 5) if n not in (0, a)])
    jump = rng.choice([0, 0, rng.randint(1, 3)])
    at_c = value + jump + rng.randint(1, 3)
    left = sp.expand(a * (x - c) + value)
    right = sp.expand(d * (x - c) + value + jump)
    function = cases((left, f"x<{c}"), (at_c, f"x={c}"), (right, f"x>{c}"))
    answer = m(value) if jump == 0 else NO_LIMIT
    verdict = "النهايتان من الجهتين متساويتان." if jump == 0 else "النهايتان مختلفتان، فالنهاية غير موجودة."
    return Problem(
        "1.1",
        f"إذا كانت ${function}$ فأوجد ${lim(c, 'f(x)')}$.",
        answer,
        wrongs(answer, m(at_c), NO_LIMIT, m(value), m(value + jump), m(value + jump + 1), m(value - 1)),
        (f"${lim(f'{c}^-', 'f(x)')}={value}$", f"${lim(f'{c}^+', 'f(x)')}={value + jump}$", verdict),
        "A",
        {"type": "one_sided", "left": left, "right": right, "at": c, "value": value if jump == 0 else None},
    )


@variant("1.1")
def limit_from_graph(rng: random.Random) -> Problem:
    """قراءة نهاية من رسم دالة مقسمة: نقطتان مفتوحتان عند c، وقيمة f(c) نقطة مغلقة أو غير معرفة."""
    c = rng.randint(-2, 2)
    left_value = rng.randint(-3, 3)
    right_value = rng.choice(
        [left_value, left_value, rng.choice([v for v in range(-3, 4) if v != left_value])]
    )
    defined = rng.random() < 0.7
    f_c = (
        rng.choice([v for v in range(-4, 5) if v not in (left_value, right_value) and (c, v) != (0, 0)])
        if defined
        else None
    )
    left = (
        left_value + rng.choice([1, -1]) * sp.Rational(rng.choice([1, 2]), 2) * (x - c) ** 2
        if rng.random() < 0.5
        else left_value + rng.choice([-1, 1, 2]) * (x - c)
    )
    right = right_value + rng.choice([-1, 1]) * sp.Rational(1, rng.choice([1, 2])) * (x - c)

    graph = Graph(Window(-5, 5, -5, 5)).add_curve(left, -5, c).add_curve(right, c, 5)
    graph.add_dot(c, left_value, closed=False)
    if right_value != left_value:
        graph.add_dot(c, right_value, closed=False)
    if f_c is not None:
        graph.add_dot(c, f_c, closed=True)

    ask = rng.choice(["both", "both", "left", "right", "value"])
    target = {
        "both": (lim(c, "f(x)"), m(left_value) if left_value == right_value else NO_LIMIT),
        "left": (lim(f"{c}^-", "f(x)"), m(left_value)),
        "right": (lim(f"{c}^+", "f(x)"), m(right_value)),
        "value": (f"f({c})", m(f_c) if f_c is not None else "غير معرفة"),
    }[ask]
    expression, answer = target
    pool = [
        m(left_value),
        m(right_value),
        m(f_c) if f_c is not None else "غير معرفة",
        NO_LIMIT,
        m(left_value + 1),
        m(right_value - 1),
        m(c),
    ]
    steps = (
        f"عند الاقتراب من ${c}$ من اليسار يقترب المنحنى من $y={left_value}$.",
        f"وعند الاقتراب من اليمين يقترب من $y={right_value}$.",
        f"النقطة المغلقة تعطي $f({c})={f_c}$."
        if f_c is not None
        else f"لا توجد نقطة مغلقة عند $x={c}$، فالدالة غير معرفة عندها.",
    )
    return Problem(
        "1.1",
        f"يبيّن الشكل التمثيل البياني للدالة $f$. أوجد ${expression}$.",
        answer,
        wrongs(answer, *pool),
        steps,
        "K",
        {
            "type": "graph_limit",
            "graph": graph.as_dict(),
            "at": c,
            "ask": ask,
            "answer": answer,
            "left": left_value,
            "right": right_value,
            "f_c": f_c,
        },
        graph=graph.as_dict(),
    )


@variant("1.2")
def limit_by_factoring(rng: random.Random) -> Problem:
    a = nz(rng, -4, 5)
    b = rng.randint(-5, 5)
    c = rng.choice([n for n in range(-5, 6) if n not in (b, -a)])
    top, bottom = sp.expand((x - a) * (x + b)), sp.expand((x - a) * (x + c))
    value = sp.Rational(a + b, a + c)
    return Problem(
        "1.2",
        f"أوجد ${lim(a, frac(top, bottom))}$.",
        m(value),
        wrongs(value, NO_LIMIT, sp.Rational(b, c) if c else 0, 0),
        (
            r"التعويض المباشر يعطي صيغة غير معينة $\frac{0}{0}$.",
            f"${frac(top, bottom)}={frac((x - a) * (x + b), (x - a) * (x + c))}={frac(x + b, x + c)}$",
            f"بالتعويض: $L={tex(value)}$",
        ),
        "A",
        {"type": "limit", "expr": top / bottom, "at": a, "value": value},
    )


@variant("1.2")
def limit_by_conjugate(rng: random.Random) -> Problem:
    p = rng.randint(2, 7)
    expr = (sp.sqrt(x + p**2) - p) / x
    value = sp.Rational(1, 2 * p)
    root = rf"\sqrt{{x+{p * p}}}"
    shown = frac(f"{root}-{p}", "x")
    return Problem(
        "1.2",
        f"أوجد ${lim(0, shown)}$.",
        m(value),
        wrongs(value, sp.Rational(1, p), 0, NO_LIMIT),
        (
            "نضرب البسط والمقام في مرافق البسط.",
            f"${shown}={frac('x', f'x({root}+{p})')}={frac(1, f'{root}+{p}')}$",
            f"بالتعويض: $L={tex(value)}$",
        ),
        "A",
        {"type": "limit", "expr": expr, "at": 0, "value": value},
    )


@variant("1.2")
def limit_at_infinity(rng: random.Random) -> Problem:
    a, c = rng.randint(2, 9), rng.randint(2, 9)
    b, d = nz(rng, -6, 6), nz(rng, -6, 6)
    top, bottom = a * x**2 + b * x + 1, c * x**2 + d * x - 2
    value = sp.Rational(a, c)
    return Problem(
        "1.2",
        f"أوجد ${lim(r'\infty', frac(top, bottom))}$.",
        m(value),
        wrongs(value, sp.Rational(b, d), 0, NO_LIMIT, sp.Rational(c, a)),
        ("نقسم البسط والمقام على $x^2$.", f"النهاية تساوي نسبة المعاملين الرئيسين: ${tex(value)}$"),
        "A",
        {"type": "limit", "expr": top / bottom, "at": sp.oo, "value": value},
    )


@variant("1.3")
def limit_sine_ratio(rng: random.Random) -> Problem:
    a, b = rng.sample(range(2, 10), 2)
    value = sp.Rational(a, b)
    return Problem(
        "1.3",
        f"أوجد ${lim(0, frac(sp.sin(a * x), b * x))}$.",
        m(value),
        wrongs(value, sp.Rational(b, a), 1, 0),
        (
            rf"نكتب الكسر بالصورة ${tex(value)}\cdot{frac(sp.sin(a * x), a * x)}$",
            rf"بما أن $\lim_{{u \to 0}}\frac{{\sin u}}{{u}}=1$ فالنهاية ${tex(value)}$",
        ),
        "A",
        {"type": "limit", "expr": sp.sin(a * x) / (b * x), "at": 0, "value": value},
    )


@variant("1.3")
def limit_tan_over_sin(rng: random.Random) -> Problem:
    a, b = rng.sample(range(2, 10), 2)
    value = sp.Rational(a, b)
    return Problem(
        "1.3",
        f"أوجد ${lim(0, frac(sp.tan(a * x), sp.sin(b * x)))}$.",
        m(value),
        wrongs(value, sp.Rational(b, a), 1, 0),
        (
            r"نقسم البسط والمقام على $x$ ونستعمل $\lim_{u \to 0}\frac{\tan u}{u}=\lim_{u \to 0}\frac{\sin u}{u}=1$",
            f"فالنهاية ${tex(value)}$",
        ),
        "A",
        {"type": "limit", "expr": sp.tan(a * x) / sp.sin(b * x), "at": 0, "value": value},
    )


@variant("1.3")
def limit_one_minus_cosine(rng: random.Random) -> Problem:
    a = rng.randint(2, 8)
    value = sp.Rational(a * a, 2)
    half = sp.Rational(a, 2)
    return Problem(
        "1.3",
        f"أوجد ${lim(0, frac(1 - sp.cos(a * x), 'x^2'))}$.",
        m(value),
        wrongs(value, a, half, 0, a * a),
        (
            rf"نستعمل $1-\cos 2u=2\sin^2 u$ مع $u={tex(half * x)}$",
            rf"فالنهاية $2\left({tex(half)}\right)^2={tex(value)}$",
        ),
        "R",
        {"type": "limit", "expr": (1 - sp.cos(a * x)) / x**2, "at": 0, "value": value},
    )


@variant("1.4")
def continuity_constant(rng: random.Random) -> Problem:
    c, k, d = nz(rng, -3, 3), nz(rng, -5, 6), rng.randint(-4, 6)
    b = c * c + d - k * c
    symbol = sp.Symbol("k")
    left, right = symbol * x + b, x**2 + d
    function = cases((left, f"x<{c}"), (right, rf"x\ge {c}"))
    return Problem(
        "1.4",
        f"أوجد قيمة الثابت $k$ التي تجعل الدالة ${function}$ متصلة عند $x={c}$.",
        m(k),
        wrongs(sp.Integer(k), -k, sp.Rational(b, c), k + 2),
        (
            f"شرط الاتصال: النهايتان من الجهتين تساويان $f({c})$.",
            f"${tex(left.subs(x, c))}={tex(right.subs(x, c))}$",
            f"$k={k}$",
        ),
        "A",
        {"type": "continuity", "left": left.subs(symbol, k), "right": right, "at": c},
    )


# الوحدة الثانية: الاشتقاق
@variant("2.1")
def average_rate(rng: random.Random) -> Problem:
    p, q, r = nz(rng, -3, 4), rng.randint(-5, 6), rng.randint(-4, 6)
    a = rng.randint(-2, 3)
    b = a + rng.randint(1, 3)
    f = p * x**2 + q * x + r
    change = f.subs(x, b) - f.subs(x, a)
    value = sp.Rational(change, b - a)
    return Problem(
        "2.1",
        f"أوجد متوسط معدل تغير الدالة $f(x)={tex(f)}$ على الفترة $[{a},{b}]$.",
        m(value),
        wrongs(value, change, sp.diff(f, x).subs(x, a), f.subs(x, a)),
        (f"${frac(f'f({b})-f({a})', minus(b, a))}={frac(change, b - a)}={tex(value)}$",),
        "A",
        {"type": "average", "f": f, "a": a, "b": b, "value": value},
    )


@variant("2.1")
def instantaneous_velocity(rng: random.Random) -> Problem:
    p, q, t0 = rng.randint(2, 6), rng.randint(1, 9), rng.randint(1, 5)
    f = p * x**2 + q * x
    d = sp.diff(f, x)
    value = d.subs(x, t0)
    shown = tex(f).replace("x", "t")
    return Problem(
        "2.1",
        f"يتحرك جسم بحيث موقعه بالأمتار بعد $t$ ثانية هو $s(t)={shown}$. أوجد سرعته اللحظية عند $t={t0}$.",
        m(value),
        wrongs(value, f.subs(x, t0), sp.Rational(f.subs(x, t0), t0), 2 * p),
        (f"$v(t)=s'(t)={tex(d).replace('x', 't')}$", f"$v({t0})={tex(value)}$"),
        "A",
        {"type": "derivative", "f": f, "at": t0, "value": value},
    )


@variant("2.2")
def derivative_as_limit_h(rng: random.Random) -> Problem:
    p, q, a = nz(rng, -3, 4), rng.randint(-5, 6), rng.randint(-3, 4)
    f = p * x**2 + q * x
    d = sp.diff(f, x)
    value = d.subs(x, a)
    return Problem(
        "2.2",
        rf"إذا كانت $f(x)={tex(f)}$ فما قيمة $\lim_{{h \to 0}}\dfrac{{f({a}+h)-f({a})}}{{h}}$؟",
        m(value),
        wrongs(value, f.subs(x, a), 2 * p * a, 0),
        (f"هذه النهاية هي تعريف $f'({a})$.", f"$f'(x)={tex(d)}$", f"$f'({a})={tex(value)}$"),
        "K",
        {"type": "derivative", "f": f, "at": a, "value": value},
    )


@variant("2.2")
def derivative_as_limit_x(rng: random.Random) -> Problem:
    p, a = rng.randint(1, 4), nz(rng, -3, 3)
    f = p * x**3
    d = sp.diff(f, x)
    value = d.subs(x, a)
    return Problem(
        "2.2",
        rf"إذا كانت $f(x)={tex(f)}$ فما قيمة $\lim_{{x \to {a}}}\dfrac{{f(x)-f({a})}}{{{tex(x - a)}}}$؟",
        m(value),
        wrongs(value, f.subs(x, a), 3 * p * a, 0),
        (f"هذه النهاية هي $f'({a})$.", f"$f'(x)={tex(d)}$", f"$f'({a})={tex(value)}$"),
        "K",
        {"type": "derivative", "f": f, "at": a, "value": value},
    )


@variant("2.3")
def power_rule_with_root(rng: random.Random) -> Problem:
    a, b = nz(rng, -3, 4), nz(rng, -6, 6)
    c = rng.choice([2, 4, 6, -2, -4])
    x0 = rng.choice([1, 4])
    f = a * x**3 + b / x + c * sp.sqrt(x)
    d = sp.diff(f, x)
    value = d.subs(x, x0)
    return Problem(
        "2.3",
        f"إذا كانت $y={tex(f)}$ فأوجد ${DYDX}$ ثم احسب قيمتها عند $x={x0}$.",
        m(value),
        wrongs(value, f.subs(x, x0), sp.diff(a * x**3 + c * sp.sqrt(x), x).subs(x, x0)),
        (
            f"نكتب $y={a}x^3{b:+d}x^{{-1}}{c:+d}x^{{1/2}}$",
            f"${DYDX}={tex(d)}$",
            f"عند $x={x0}$ القيمة ${tex(value)}$",
        ),
        "A",
        {"type": "derivative", "f": f, "at": x0, "value": value},
    )


@variant("2.3")
def power_rule_negative_exponent(rng: random.Random) -> Problem:
    a, b, c = nz(rng, -3, 4), nz(rng, -5, 5), rng.randint(-6, 6)
    x0 = rng.choice([-2, -1, 1, 2])
    f = a * x**4 + b / x**2 + c
    d = sp.diff(f, x)
    value = d.subs(x, x0)
    return Problem(
        "2.3",
        f"إذا كانت $y={tex(f)}$ فأوجد ${DYDX}$ ثم احسب قيمتها عند $x={x0}$.",
        m(value),
        wrongs(value, f.subs(x, x0), 4 * a * x0**3),
        (f"نكتب الحد الكسري بالصورة ${b}x^{{-2}}$", f"${DYDX}={tex(d)}$", f"القيمة ${tex(value)}$"),
        "A",
        {"type": "derivative", "f": f, "at": x0, "value": value},
    )


@variant("2.4")
def product_rule(rng: random.Random) -> Problem:
    a, b, c = nz(rng, -3, 4), nz(rng, -5, 5), nz(rng, -5, 6)
    x0 = rng.randint(-2, 3)
    u, v = a * x + b, x**2 + c
    value = sp.diff(u * v, x).subs(x, x0)
    return Problem(
        "2.4",
        f"إذا كانت $y=({tex(u)})({tex(v)})$ فأوجد قيمة ${DYDX}$ عند $x={x0}$.",
        m(value),
        wrongs(value, a * 2 * x0, (u * v).subs(x, x0), a * v.subs(x, x0)),
        (
            rf"$u={tex(u)},\ v={tex(v)},\ u'={a},\ v'=2x$",
            f"${DYDX}=u'v+uv'=({a})({tex(v)})+({tex(u)})(2x)$",
            f"عند $x={x0}$ القيمة ${tex(value)}$",
        ),
        "A",
        {"type": "derivative", "f": u * v, "at": x0, "value": value},
    )


@variant("2.4")
def quotient_rule(rng: random.Random) -> Problem:
    a, c = nz(rng, -4, 5), nz(rng, -3, 4)
    b = rng.randint(-5, 5)
    d = rng.choice([n for n in range(-5, 6) if a * n - b * c != 0])
    x0 = rng.choice([n for n in range(-2, 4) if c * n + d != 0])
    u, v = a * x + b, c * x + d
    value = sp.Rational(a * d - b * c, (c * x0 + d) ** 2)
    square = f"({tex(v)})^2"
    return Problem(
        "2.4",
        f"إذا كانت $y={frac(u, v)}$ فأوجد قيمة ${DYDX}$ عند $x={x0}$.",
        m(value),
        wrongs(value, -value, sp.Rational(a, c), (u / v).subs(x, x0)),
        (
            rf"${DYDX}=\dfrac{{u'v-uv'}}{{v^2}}={frac(f'({a})({tex(v)})-({tex(u)})({c})', square)}$",
            f"${DYDX}={frac(a * d - b * c, square)}$",
            f"عند $x={x0}$ القيمة ${tex(value)}$",
        ),
        "A",
        {"type": "derivative", "f": u / v, "at": x0, "value": value},
    )


@variant("2.5")
def chain_power(rng: random.Random) -> Problem:
    a, b = nz(rng, -2, 3), nz(rng, -3, 4)
    n, x0 = rng.randint(2, 4), rng.choice([-1, 1, 2])
    inner = a * x**2 + b
    f = inner**n
    value = sp.diff(f, x).subs(x, x0)
    return Problem(
        "2.5",
        f"إذا كانت $y=({tex(inner)})^{n}$ فأوجد قيمة ${DYDX}$ عند $x={x0}$.",
        m(value),
        wrongs(value, n * inner.subs(x, x0) ** (n - 1), f.subs(x, x0), 2 * a * x0),
        (
            rf"${DYDX}={n}({tex(inner)})^{{{n - 1}}}\cdot({tex(sp.diff(inner, x))})$",
            f"عند $x={x0}$ القيمة ${tex(value)}$",
        ),
        "A",
        {"type": "derivative", "f": f, "at": x0, "value": value},
    )


@variant("2.5")
def chain_root(rng: random.Random) -> Problem:
    a, root = rng.randint(1, 6), rng.randint(2, 6)
    x0 = rng.randint(1, 5)
    b = root**2 - a * x0
    f = sp.sqrt(a * x + b)
    value = sp.Rational(a, 2 * root)
    return Problem(
        "2.5",
        f"إذا كانت $y={tex(f)}$ فأوجد قيمة ${DYDX}$ عند $x={x0}$.",
        m(value),
        wrongs(value, sp.Rational(1, 2 * root), sp.Integer(root), sp.Rational(a, root)),
        (f"${DYDX}={frac(a, 2 * f)}$", f"عند $x={x0}$ القيمة ${tex(value)}$"),
        "A",
        {"type": "derivative", "f": f, "at": x0, "value": value},
    )


@variant("2.6")
def derivative_log_quadratic(rng: random.Random) -> Problem:
    a, b = rng.randint(1, 6), rng.randint(1, 9)
    inner = a * x**2 + b
    f, d = sp.log(inner), 2 * a * x / inner
    return Problem(
        "2.6",
        f"أوجد ${DYDX}$ إذا كانت $y={tex(f)}$.",
        m(d),
        wrongs(d, 1 / inner, 2 * a * x, a * x / inner),
        (rf"${DYDX}=\dfrac{{u'}}{{u}}$ حيث $u={tex(inner)}$", f"${DYDX}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 1},
    )


@variant("2.6")
def derivative_x_exponential(rng: random.Random) -> Problem:
    a = nz(rng, -4, 5)
    e = sp.exp(a * x)
    f, d = x * e, (1 + a * x) * e
    return Problem(
        "2.6",
        f"أوجد ${DYDX}$ إذا كانت $y={tex(f)}$.",
        m(d),
        wrongs(d, a * e, e, (x + a) * e),
        (rf"قاعدة الضرب: $u=x,\ v={tex(e)}$", rf"${DYDX}={tex(e)}+x\cdot {tex(a * e)}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 1},
    )


@variant("2.6")
def derivative_power_log(rng: random.Random) -> Problem:
    n = rng.randint(2, 5)
    f = x**n * sp.log(x)
    d = n * x ** (n - 1) * sp.log(x) + x ** (n - 1)
    return Problem(
        "2.6",
        f"أوجد ${DYDX}$ إذا كانت $y={tex(f)}$ حيث $x>0$.",
        m(d),
        wrongs(d, n * x ** (n - 1) / x, n * x ** (n - 1) * sp.log(x), x ** (n - 1)),
        (rf"قاعدة الضرب: $u=x^{n},\ v=\ln x$", f"${DYDX}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 1, "positive": True},
    )


@variant("2.7")
def derivative_sine_cosine(rng: random.Random) -> Problem:
    a, b, n = nz(rng, -4, 5), nz(rng, -4, 5), rng.randint(2, 5)
    s, c = sp.sin(n * x), sp.cos(n * x)
    f, d = a * s + b * c, a * n * c - b * n * s
    return Problem(
        "2.7",
        f"أوجد ${DYDX}$ إذا كانت $y={tex(f)}$.",
        m(d),
        wrongs(d, a * c - b * s, a * n * c + b * n * s, -d),
        (f"نشتق كل حد بقاعدة السلسلة، والمشتقة الداخلية ${n}$.", f"${DYDX}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 1},
    )


@variant("2.7")
def derivative_tangent(rng: random.Random) -> Problem:
    n = rng.randint(2, 6)
    f, d = sp.tan(n * x), n * sp.sec(n * x) ** 2
    return Problem(
        "2.7",
        f"أوجد ${DYDX}$ إذا كانت $y={tex(f)}$.",
        m(d),
        wrongs(d, sp.sec(n * x) ** 2, n * sp.sec(n * x), -n * sp.csc(n * x) ** 2),
        (r"$\dfrac{d}{dx}\tan u=u'\sec^2 u$", f"${DYDX}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 1},
    )


@variant("2.7")
def derivative_x_sine(rng: random.Random) -> Problem:
    n = rng.randint(2, 5)
    s, c = sp.sin(n * x), sp.cos(n * x)
    f, d = x * s, s + n * x * c
    return Problem(
        "2.7",
        f"أوجد ${DYDX}$ إذا كانت $y={tex(f)}$.",
        m(d),
        wrongs(d, n * c, s + x * c, s - n * x * c),
        (rf"قاعدة الضرب: $u=x,\ v={tex(s)}$", f"${DYDX}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 1},
    )


@variant("2.8")
def implicit_circle(rng: random.Random) -> Problem:
    p, q, r = rng.choice([(3, 4, 5), (4, 3, 5), (6, 8, 10), (8, 6, 10), (5, 12, 13), (12, 5, 13)])
    p, q = p * rng.choice([1, -1]), q * rng.choice([1, -1])
    value = sp.Rational(-p, q)
    return Problem(
        "2.8",
        f"أوجد ${DYDX}$ عند النقطة $({p},{q})$ على المنحنى $x^2+y^2={r * r}$.",
        m(value),
        wrongs(value, -value, sp.Rational(q, p), sp.Rational(-q, p)),
        (f"$2x+2y{DYDX}=0$", f"${DYDX}=-\\dfrac{{x}}{{y}}$", f"عند النقطة القيمة ${tex(value)}$"),
        "A",
        {"type": "implicit", "F": x**2 + y**2 - r * r, "point": (p, q), "value": value},
    )


@variant("2.8")
def implicit_mixed_term(rng: random.Random) -> Problem:
    a = rng.choice([1, 3])  # المعامل 2 يجعل المنحنى مربعًا كاملًا، أي مستقيمين
    p = nz(rng, -3, 3)
    q = rng.choice([n for n in range(-3, 4) if n != 0 and a * p + 2 * n != 0])
    c = p * p + a * p * q + q * q
    value = sp.Rational(-(2 * p + a * q), a * p + 2 * q)
    curve = tex(x**2 + a * x * y + y**2)
    return Problem(
        "2.8",
        f"أوجد ${DYDX}$ عند النقطة $({p},{q})$ على المنحنى ${curve}={c}$.",
        m(value),
        wrongs(value, -value, sp.Rational(-p, q), sp.Rational(-q, p)),
        (
            rf"$2x+{a}\left(y+x{DYDX}\right)+2y{DYDX}=0$",
            f"${DYDX}={frac(-(2 * x + a * y), a * x + 2 * y)}$",
            f"عند النقطة القيمة ${tex(value)}$",
        ),
        "R",
        {"type": "implicit", "F": x**2 + a * x * y + y**2 - c, "point": (p, q), "value": value},
    )


@variant("2.9")
def second_derivative_polynomial(rng: random.Random) -> Problem:
    a, b, c = nz(rng, -3, 3), nz(rng, -4, 5), rng.randint(-6, 6)
    x0 = rng.randint(-2, 2)
    f = a * x**4 + b * x**3 + c * x
    first, second = sp.diff(f, x), sp.diff(f, x, 2)
    value = second.subs(x, x0)
    return Problem(
        "2.9",
        f"إذا كانت $f(x)={tex(f)}$ فأوجد $f''({x0})$.",
        m(value),
        wrongs(value, first.subs(x, x0), f.subs(x, x0), sp.diff(f, x, 3).subs(x, x0)),
        (f"$f'(x)={tex(first)}$", f"$f''(x)={tex(second)}$", f"$f''({x0})={tex(value)}$"),
        "A",
        {"type": "derivative", "f": f, "at": x0, "value": value, "order": 2},
    )


@variant("2.9")
def third_derivative_exponential(rng: random.Random) -> Problem:
    a = rng.choice([-3, -2, 2, 3, 4])
    f = sp.exp(a * x)
    d = a**3 * f
    return Problem(
        "2.9",
        rf"أوجد $\dfrac{{d^3y}}{{dx^3}}$ إذا كانت $y={tex(f)}$.",
        m(d),
        wrongs(d, a**2 * f, 3 * a * f, a * f),
        (f"كل اشتقاق يضرب الدالة في ${a}$.", rf"$\dfrac{{d^3y}}{{dx^3}}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 3},
    )


@variant("2.9")
def second_derivative_sine(rng: random.Random) -> Problem:
    n = rng.randint(2, 6)
    f = sp.sin(n * x)
    d = -(n**2) * f
    return Problem(
        "2.9",
        rf"أوجد $\dfrac{{d^2y}}{{dx^2}}$ إذا كانت $y={tex(f)}$.",
        m(d),
        wrongs(d, -d, n * sp.cos(n * x), -n * f),
        (f"${DYDX}={tex(n * sp.cos(n * x))}$", rf"$\dfrac{{d^2y}}{{dx^2}}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 2},
    )


# الوحدة الثالثة: تطبيقات الاشتقاق
@variant("3.1")
def monotonic_intervals(rng: random.Random) -> Problem:
    f, p, q, sign = cubic_with_critical_points(rng)
    ask_increasing = rng.choice([True, False])
    middle, outer = f"$({p},{q})$", rf"$(-\infty,{p})\cup({q},\infty)$"
    inner_increasing = sign < 0
    answer = middle if ask_increasing == inner_increasing else outer
    word = "تزايد" if ask_increasing else "تناقص"
    return Problem(
        "3.1",
        f"حدد فترات {word} الدالة $f(x)={tex(f)}$.",
        answer,
        wrongs(answer, middle, outer, rf"$(-\infty,{q})$", rf"$({p},\infty)$"),
        (
            f"$f'(x)={tex(sp.factor(sp.diff(f, x)))}$",
            f"النقطتان الحرجتان $x={p}$ و$x={q}$.",
            f"من إشارة المشتقة: فترات ال{word} {answer}",
        ),
        "A",
        {
            "type": "monotonic",
            "f": f,
            "p": p,
            "q": q,
            "inner_increasing": inner_increasing,
            "ask": ask_increasing,
            "answer_inner": answer == middle,
        },
    )


@variant("3.2")
def local_extremum(rng: random.Random) -> Problem:
    f, p, q, sign = cubic_with_critical_points(rng)
    want_max = rng.choice([True, False])
    where = p if want_max == (sign > 0) else q
    other = q if where == p else p
    value = f.subs(x, where)
    word = "العظمى" if want_max else "الصغرى"
    return Problem(
        "3.2",
        f"أوجد القيمة {word} المحلية للدالة $f(x)={tex(f)}$.",
        m(value),
        wrongs(value, f.subs(x, other), sp.Integer(where), sp.Integer(other)),
        (
            f"$f'(x)={tex(sp.factor(sp.diff(f, x)))}$",
            f"$f''(x)={tex(sp.diff(f, x, 2))}$",
            f"عند $x={where}$ القيمة {word} المحلية ${tex(value)}$",
        ),
        "A",
        {"type": "local", "f": f, "at": where, "value": value, "max": want_max},
    )


@variant("3.2")
def absolute_extremum(rng: random.Random) -> Problem:
    f, p, q, _sign = cubic_with_critical_points(rng)
    low, high = p - 1, q + 1
    values = {point: f.subs(x, point) for point in (low, p, q, high)}
    want_max = rng.choice([True, False])
    value = max(values.values()) if want_max else min(values.values())
    other = min(values.values()) if want_max else max(values.values())
    word = "العظمى" if want_max else "الصغرى"
    table = "، ".join(f"$f({point})={tex(val)}$" for point, val in values.items())
    return Problem(
        "3.2",
        f"أوجد القيمة {word} المطلقة للدالة $f(x)={tex(f)}$ على الفترة $[{low},{high}]$.",
        m(value),
        wrongs(value, other, *values.values()),
        (
            f"النقطتان الحرجتان $x={p}$ و$x={q}$ داخل الفترة.",
            f"نقارن القيم: {table}",
            f"القيمة {word} المطلقة ${tex(value)}$",
        ),
        "R",
        {"type": "absolute", "f": f, "low": low, "high": high, "value": value, "max": want_max},
    )


def inflection_cubic(rng: random.Random) -> tuple[sp.Expr, int, int]:
    t, sign = rng.randint(-3, 3), rng.choice([1, 1, -1])
    c, d = rng.randint(-6, 6), rng.randint(-5, 6)
    return sign * (x**3 - 3 * t * x**2) + c * x + d, t, sign


@variant("3.3")
def inflection_point(rng: random.Random) -> Problem:
    f, t, _sign = inflection_cubic(rng)
    value = f.subs(x, t)
    answer = f"$({t},{tex(value)})$"
    mirror = -t if t else 1
    return Problem(
        "3.3",
        f"أوجد نقطة الانعطاف لمنحنى الدالة $f(x)={tex(f)}$.",
        answer,
        wrongs(
            answer,
            f"$({t},{tex(value + 1)})$",
            f"$({mirror},{tex(f.subs(x, mirror))})$",
            f"$({tex(value)},{t})$",
            f"$({t + 1},{tex(f.subs(x, t + 1))})$",
        ),
        (
            f"$f''(x)={tex(sp.diff(f, x, 2))}$",
            f"$f''(x)=0$ عند $x={t}$ وتتغير الإشارة عندها.",
            f"النقطة {answer}",
        ),
        "A",
        {"type": "inflection", "f": f, "at": t, "value": value},
    )


@variant("3.3")
def concavity_interval(rng: random.Random) -> Problem:
    f, t, sign = inflection_cubic(rng)
    up = rng.choice([True, False])
    right_side = up == (sign > 0)
    right, left = rf"$({t},\infty)$", rf"$(-\infty,{t})$"
    answer, other = (right, left) if right_side else (left, right)
    word = "لأعلى" if up else "لأسفل"
    return Problem(
        "3.3",
        f"حدد الفترة التي يكون فيها منحنى $f(x)={tex(f)}$ مقعرًا {word}.",
        answer,
        wrongs(answer, other, r"$(-\infty,\infty)$", rf"$({t + 1},\infty)$", rf"$(-\infty,{t + 1})$"),
        (f"$f''(x)={tex(sp.diff(f, x, 2))}$", f"من إشارة المشتقة الثانية: الفترة {answer}"),
        "A",
        {"type": "concavity", "f": f, "at": t, "up": up, "right_side": right_side},
    )


@variant("3.3")
def full_concavity_study(rng: random.Random) -> Problem:
    f, t, sign = inflection_cubic(rng)
    value = f.subs(x, t)
    right, left = rf"$({t},\infty)$", rf"$(-\infty,{t})$"
    up, down = (right, left) if sign > 0 else (left, right)
    answer = f"مقعر لأعلى على {up}، ولأسفل على {down}، ونقطة الانعطاف $({t},{tex(value)})$"
    return Problem(
        "3.3",
        f"ادرس تقعر منحنى الدالة $f(x)={tex(f)}$، ثم أوجد نقطة انعطافه.",
        answer,
        (),
        (f"$f''(x)={tex(sp.diff(f, x, 2))}$", f"$f''(x)=0$ عند $x={t}$.", answer),
        "A",
        {"type": "inflection", "f": f, "at": t, "value": value},
        mcq_ok=False,
    )


def with_unit(value: Any, unit: str) -> str:
    return f"${tex(value)}$ {unit}"


@variant("3.5")
def fence_against_wall(rng: random.Random) -> Problem:
    length = 4 * rng.randint(5, 30)
    area = length * x - 2 * x**2
    width = sp.Rational(length, 4)
    value = width * sp.Rational(length, 2)
    unit = "مترًا مربعًا"
    answer = with_unit(value, unit)
    return Problem(
        "3.5",
        f"لدى مزارع سياج طوله ${length}$ مترًا، ويريد إحاطة حظيرة مستطيلة بجانب جدار مستقيم لا يحتاج إلى سياج. "
        "أوجد أكبر مساحة ممكنة للحظيرة.",
        answer,
        wrongs(answer, *[with_unit(v, unit) for v in (width**2, 4 * width**2, 3 * width**2)]),
        (
            f"إذا كان عرض الحظيرة $x$ فطولها ${tex(length - 2 * x)}$ والمساحة $A(x)={tex(area)}$.",
            f"$A'(x)={tex(sp.diff(area, x))}=0$ عند $x={tex(width)}$.",
            "$A''(x)=-4<0$ فهي قيمة عظمى.",
            f"أكبر مساحة {answer}.",
        ),
        "R",
        {
            "type": "optimum",
            "f": area,
            "low": 0,
            "high": sp.Rational(length, 2),
            "arg": width,
            "value": value,
            "max": True,
        },
    )


@variant("3.5")
def open_box(rng: random.Random) -> Problem:
    n = rng.randint(1, 8)
    side = 6 * n
    volume = x * (side - 2 * x) ** 2
    value = volume.subs(x, n)
    unit = "سنتيمترًا مكعبًا"
    answer = with_unit(value, unit)
    others = (2 * n, sp.Rational(n, 2), sp.Rational(3 * n, 2))
    return Problem(
        "3.5",
        f"صفيحة مربعة طول ضلعها ${side}$ سنتيمترًا، قُصّ من كل ركن منها مربع طول ضلعه $x$ "
        "ثم ثُنيت الجوانب لعمل صندوق مفتوح. أوجد أكبر حجم ممكن للصندوق.",
        answer,
        wrongs(answer, *[with_unit(volume.subs(x, v), unit) for v in others]),
        (
            f"$V(x)=x({tex(side - 2 * x)})^2$ حيث $0<x<{3 * n}$.",
            f"$V'(x)={tex(sp.factor(sp.diff(volume, x)))}=0$ داخل المجال عند $x={n}$.",
            f"أكبر حجم {answer}.",
        ),
        "R",
        {"type": "optimum", "f": volume, "low": 0, "high": 3 * n, "arg": n, "value": value, "max": True},
    )


@variant("3.5")
def minimum_sum_of_squares(rng: random.Random) -> Problem:
    total = 2 * rng.randint(3, 25)
    objective = x**2 + (total - x) ** 2
    half = sp.Rational(total, 2)
    value = objective.subs(x, half)
    return Problem(
        "3.5",
        f"عددان حقيقيان مجموعهما ${total}$. أوجد أصغر قيمة ممكنة لمجموع مربعيهما.",
        m(value),
        wrongs(value, half**2, sp.Integer(total) ** 2, objective.subs(x, half + 1)),
        (
            f"$S(x)=x^2+({tex(total - x)})^2$",
            f"$S'(x)={tex(sp.expand(sp.diff(objective, x)))}=0$ عند $x={tex(half)}$.",
            f"$S''(x)=4>0$ فأصغر قيمة ${tex(value)}$",
        ),
        "A",
        {
            "type": "optimum",
            "f": objective,
            "low": -100,
            "high": 100,
            "arg": half,
            "value": value,
            "max": False,
        },
    )


# مولّدات الرسوم والمستويات في وحدتين مستقلتين تسجّلان نفسيهما في REGISTRY عند الاستيراد.
from . import graph_problems, level_problems  # noqa: E402, F401, I001
