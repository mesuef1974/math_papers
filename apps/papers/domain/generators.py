"""مولّدات مسائل أصلية بالمعاملات، بلا نص من أي كتاب. وحدة نقية لا تعرف Django.

كل مولّد يبني المسألة عكسيًا من حلها حتى تخرج الأرقام نظيفة. النص يحمل الرياضيات بين علامتي $.
الحقل check يصف المسألة لاختبار مستقل يتحقق من الجواب عدديًا، لا بالطريقة التي بُني بها.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field, replace
from functools import cache
from itertools import product
from typing import Any

import sympy as sp

from apps.curriculum.courses import DEFAULT_COURSE

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
    variant: str = field(default="", compare=False)  # اسم الصيغة التي ولّدتها؛ يضعه generate()

    @property
    def key(self) -> str:
        """هوية المسألة لمنع التكرار في الورقة: النص، ومعه الرسم لأن أسئلة الرسوم تتشابه نصًا."""
        return (
            self.stem
            if self.graph is None
            else f"{self.stem}|{self.graph['curves'][:1]}|{self.graph['dots']}"
        )

    @property
    def fingerprint(self) -> str:
        """بصمة قصيرة ثابتة للمسألة، تُحفظ مع الورقة ليُستبدل جزء دون تكرار ما بقي."""
        return hashlib.sha1(self.key.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


Generator = Callable[[random.Random], Problem]
# المفتاح (معرّف المقرر، رمز الدرس): رمز الدرس وحده يتكرر بين المقررات.
REGISTRY: dict[tuple[str, str], list[Generator]] = {}
# رقم مثال الكتاب الذي تقيس الصيغة مهارته، بمفتاح (مقرر، درس، اسم الصيغة). يلزم كل مقرر له نطاق اختبار:
# فيه أمثلة إثرائية لا يُبنى عليها سؤال (انظر out_of_scope).
SKILL_EXAMPLES: dict[tuple[str, str, str], int] = {}


def variant(
    lesson: str, course: str = DEFAULT_COURSE, example: int | None = None
) -> Callable[[Generator], Generator]:
    def register(fn: Generator) -> Generator:
        REGISTRY.setdefault((course, lesson), []).append(fn)
        if example is not None:
            SKILL_EXAMPLES[(course, lesson, fn.__name__)] = example
        return fn

    return register


def skill_example(course: str, lesson: str, name: str) -> int | None:
    """رقم مثال الكتاب الذي تقيس الصيغة مهارته، أو None لصيغة لم تصرّح به."""
    return SKILL_EXAMPLES.get((course, lesson, name))


def out_of_scope(
    course: str, enrichment_lessons: Collection[str], enrichment_examples: Mapping[str, Collection[int]]
) -> list[str]:
    """صيغ المقرر الخارجة عن نطاق الاختبار: درس إثرائي، أو مثال إثرائي، أو صيغة لم تصرّح بمثالها."""
    found = []
    for (registered, lesson), fns in sorted(REGISTRY.items()):
        if registered != course:
            continue
        for fn in fns:
            example = SKILL_EXAMPLES.get((course, lesson, fn.__name__))
            if lesson in enrichment_lessons:
                found.append(f"{lesson}:{fn.__name__} درس إثرائي")
            elif example is None:
                found.append(f"{lesson}:{fn.__name__} بلا رقم مثال")
            elif example in enrichment_examples.get(lesson, ()):
                found.append(f"{lesson}:{fn.__name__} مثال إثرائي {example}")
    return found


class LevelUnavailableError(LookupError):
    """لا توجد صيغة للدرس بهذا المستوى ونوع السؤال."""


def available_lessons(course: str = DEFAULT_COURSE) -> set[str]:
    return {lesson for registered, lesson in REGISTRY if registered == course}


def generator_version(course: str = DEFAULT_COURSE) -> str:
    """بصمة مجموعة الصيغ. أي صيغة تُضاف أو تُحذف تغيّر ترتيب الاختيار، فتُحفظ مع كل ورقة لتفسير اختلاف إعادة التوليد."""
    # بصمة كل مقرر من صيغه وحدها: صيغة مقرر جديد لا تغيّر بصمة أوراق الثاني عشر المحفوظة (والصيغة كما قبل المقررات).
    names = sorted(
        f"{lesson}:{fn.__name__}"
        for (registered, lesson), fns in REGISTRY.items()
        if registered == course
        for fn in fns
    )
    return hashlib.sha1("\n".join(names).encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def diversity_report(seeds: int = 60) -> list[dict[str, Any]]:
    """لكل صيغة: كم مسألة مختلفة تعطي عبر بذور متتابعة. يفضح الصيغ ضيقة المعاملات التي تكرر نفسها."""
    rows = []
    for (course, lesson), fns in sorted(REGISTRY.items()):
        for fn in fns:
            keys = {fn(random.Random(seed)).key for seed in range(seeds)}  # noqa: S311 — بذور ثابتة لا أمنية
            levels = variant_profile(fn)[0]
            rows.append(
                {
                    "course": course,
                    "lesson": lesson,
                    "variant": fn.__name__,
                    "levels": "".join(level for level in LEVEL_NAMES if level in levels),
                    "distinct": len(keys),
                    "seeds": seeds,
                }
            )
    return rows


def warm_profiles() -> None:
    for fns in REGISTRY.values():
        for fn in fns:
            variant_profile(fn)


@cache
def variant_profile(fn: Generator) -> tuple[frozenset[str], bool, bool, bool]:
    """(المستويات، يصلح للموضوعي، يصلح للمقالي، فيه رسم) لصيغة واحدة، من عينات ثابتة."""
    samples = [fn(random.Random(seed)) for seed in range(LEVEL_SAMPLES)]  # noqa: S311 — عينات ثابتة لا أمنية
    return (
        frozenset(p.level for p in samples),
        all(p.mcq_ok for p in samples),
        all(p.essay_ok for p in samples),
        all(p.graph is not None or bool(p.option_graphs) for p in samples),
    )


def variants(
    lesson: str,
    kind: str = "essay",
    level: str | None = None,
    graph: bool = False,
    course: str = DEFAULT_COURSE,
) -> list[Generator]:
    """graph=True يحصر الصيغ في أسئلة الرسم؛ False لا يقيّد."""
    pool = []
    for fn in REGISTRY.get((course, lesson), []):
        levels, mcq_ok, essay_ok, has_graph = variant_profile(fn)
        if (
            (mcq_ok if kind == "mcq" else essay_ok)
            and (level is None or level in levels)
            and (has_graph or not graph)
        ):
            pool.append(fn)
    return pool


def lesson_levels(lesson: str, kind: str = "essay", course: str = DEFAULT_COURSE) -> list[str]:
    found: set[str] = set()
    for fn in variants(lesson, kind, course=course):
        found |= variant_profile(fn)[0]
    return [level for level in LEVEL_NAMES if level in found]


class ExhaustedError(ValueError):
    """نفدت المحاولات دون مسألة جديدة تخالف ما في الورقة."""


def generate(
    lesson: str,
    rng: random.Random,
    kind: str = "essay",
    avoid: set[str] | None = None,
    level: str | None = None,
    graph: bool = False,
    variant_name: str | None = None,
    course: str = DEFAULT_COURSE,
) -> Problem:
    """يختار صيغة من مولّدات الدرس بالمستوى المطلوب (وبرسم إن طُلب)، ويتفادى ما ظهر في الورقة نفسها.

    variant_name يحصر الاختيار في صيغة واحدة بالاسم، فيُبنى نموذج B بالبنية نفسها وأرقام مختلفة.
    """
    avoid = avoid if avoid is not None else set()
    pool = variants(lesson, kind, level, graph, course)
    if variant_name is not None:
        pool = [fn for fn in pool if fn.__name__ == variant_name]
    if not pool:
        raise LevelUnavailableError(
            f"{lesson}/{kind}/{level}/{'graph' if graph else ''}/{variant_name or ''}"
        )
    for _ in range(MAX_ATTEMPTS):
        fn = rng.choice(pool)
        problem = replace(fn(rng), variant=fn.__name__)
        fits = problem.mcq_ok if kind == "mcq" else problem.essay_ok
        # avoid يقبل مفاتيح المسائل (داخل التوليد) وبصماتها (من ورقة محفوظة عند الاستبدال)
        if (
            fits
            and problem.key not in avoid
            and problem.fingerprint not in avoid
            and (level is None or problem.level == level)
        ):
            return problem
    raise ExhaustedError(f"تعذر توليد مسألة جديدة للدرس {lesson}")


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
    return rf"\lim\limits_{{x \to {tex(at)}}} {body}"


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
@variant("1.1", example=2)
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


@variant("1.1", example=3)
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


@variant("1.2", example=3)
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


@variant("1.2", example=4)
def limit_by_conjugate(rng: random.Random) -> Problem:
    p, k = rng.randint(2, 7), rng.randint(1, 4)
    expr = (sp.sqrt(k * x + p**2) - p) / x
    value = sp.Rational(k, 2 * p)
    kx = "x" if k == 1 else f"{k}x"
    root = rf"\sqrt{{{kx}+{p * p}}}"
    shown = frac(f"{root}-{p}", "x")
    return Problem(
        "1.2",
        f"أوجد ${lim(0, shown)}$.",
        m(value),
        wrongs(value, sp.Rational(k, p), 0, NO_LIMIT, sp.Rational(1, 2 * p)),
        (
            "نضرب البسط والمقام في مرافق البسط.",
            f"${shown}={frac(kx, f'x({root}+{p})')}={frac(k, f'{root}+{p}')}$",
            f"بالتعويض: $L={tex(value)}$",
        ),
        "A",
        {"type": "limit", "expr": expr, "at": 0, "value": value},
    )


@variant("1.2", example=6)
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


@variant("1.3", example=2)
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
            rf"بما أن $\lim\limits_{{u \to 0}}\frac{{\sin u}}{{u}}=1$ فالنهاية ${tex(value)}$",
        ),
        "A",
        {"type": "limit", "expr": sp.sin(a * x) / (b * x), "at": 0, "value": value},
    )


@variant("1.3", example=4)
def limit_tan_over_sin(rng: random.Random) -> Problem:
    a, b = rng.sample(range(2, 10), 2)
    value = sp.Rational(a, b)
    return Problem(
        "1.3",
        f"أوجد ${lim(0, frac(sp.tan(a * x), sp.sin(b * x)))}$.",
        m(value),
        wrongs(value, sp.Rational(b, a), 1, 0),
        (
            r"نقسم البسط والمقام على $x$ ونستعمل $\lim\limits_{u \to 0}\frac{\tan u}{u}=\lim\limits_{u \to 0}\frac{\sin u}{u}=1$",
            f"فالنهاية ${tex(value)}$",
        ),
        "A",
        {"type": "limit", "expr": sp.tan(a * x) / sp.sin(b * x), "at": 0, "value": value},
    )


@variant("1.3", example=3)
def limit_one_minus_cosine(rng: random.Random) -> Problem:
    a, b = rng.randint(2, 9), rng.randint(1, 4)
    value = sp.Rational(a * a, 2 * b)
    half = sp.Rational(a, 2)
    bottom = "x^2" if b == 1 else f"{b}x^2"
    return Problem(
        "1.3",
        f"أوجد ${lim(0, frac(1 - sp.cos(a * x), bottom))}$.",
        m(value),
        wrongs(value, a, half, 0, a * a, sp.Rational(a * a, 2)),
        (
            rf"نستعمل $1-\cos 2u=2\sin^2 u$ مع $u={tex(half * x)}$",
            rf"فالنهاية $\dfrac{{2\left({tex(half)}\right)^2}}{{{b}}}={tex(value)}$",
        ),
        "R",
        {"type": "limit", "expr": (1 - sp.cos(a * x)) / (b * x**2), "at": 0, "value": value},
    )


@variant("1.4", example=2)
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


POS_INF, NEG_INF = r"$+\infty$", r"$-\infty$"


def infinity(sign: int) -> str:
    return POS_INF if sign > 0 else NEG_INF


@variant("1.1", example=1)
def limit_from_table(rng: random.Random) -> Problem:
    """نهاية كسر غير معرف عند نقطة (صيغة 0/0) من قيم قريبة من الجهتين."""
    a = nz(rng, -4, 5)
    b = rng.choice([n for n in range(-5, 6) if n != -a])
    top = sp.expand((x - a) * (x + b))
    value = a + b
    near = (sp.Rational(a * 100 - 1, 100), sp.Rational(a * 100 + 1, 100))
    rows = "، ".join(f"$f({float(p):.2f})={float(p + b):.2f}$" for p in near)
    return Problem(
        "1.1",
        f"الدالة $f(x)={frac(top, x - a)}$ غير معرفة عند $x={a}$. "
        f"قدّر ${lim(a, 'f(x)')}$ من جدول قيم قريبة من ${a}$ من الجهتين.",
        m(value),
        wrongs(sp.Integer(value), NO_LIMIT, 0, a, b),
        (
            rf"التعويض المباشر يعطي $\frac{{0}}{{0}}$، فنحسب قيمًا قريبة من ${a}$: {rows}.",
            f"قيم الجهتين تقترب من ${value}$ كلما اقتربت $x$ من ${a}$.",
            f"${lim(a, 'f(x)')}={value}$",
        ),
        "K",
        {"type": "table_limit", "top": top, "bottom": x - a, "at": a, "value": value},
    )


@variant("1.1", example=4)
def infinite_limit_sides(rng: random.Random) -> Problem:
    """نهايتا الجهتين لدالة نسبية عند صفر مقامها: +∞ أو −∞، والنهاية من الجهتين غير موجودة."""
    c, k = rng.randint(-4, 4), nz(rng, -6, 6)
    side = rng.choice(["-", "+", "both"])
    answer = NO_LIMIT if side == "both" else infinity(k if side == "+" else -k)
    at = c if side == "both" else f"{c}^{side}"
    return Problem(
        "1.1",
        f"إذا كانت $f(x)={frac(k, x - c)}$ فأوجد ${lim(at, 'f(x)')}$.",
        answer,
        wrongs(answer, POS_INF, NEG_INF, NO_LIMIT, "$0$", m(k)),
        (
            f"المقام ${tex(x - c)}$ يؤول إلى $0$ والبسط ${k}$ ثابت، فالقيم تكبر بلا حد.",
            f"من اليسار المقام سالب فالكسر يؤول إلى {infinity(-k)}، ومن اليمين موجب فيؤول إلى {infinity(k)}.",
            "النهايتان مختلفتان فالنهاية غير موجودة." if side == "both" else f"فالنهاية {answer}.",
        ),
        "A",
        {"type": "infinite_side", "expr": k / (x - c), "at": c, "side": side, "answer": answer},
    )


@variant("1.1", example=5)
def infinite_limit_square(rng: random.Random) -> Problem:
    """مقام مربع: الجهتان تتفقان على +∞ أو −∞ بإشارة البسط."""
    c, k, d = rng.randint(-4, 4), nz(rng, -6, 6), rng.randint(-3, 3)
    shift = f"+{d}" if d > 0 else (f"{d}" if d < 0 else "")
    shown = frac(k, f"({tex(x - c)})^2") + shift
    answer = infinity(k)
    return Problem(
        "1.1",
        f"إذا كانت $f(x)={shown}$ فأوجد ${lim(c, 'f(x)')}$.",
        answer,
        wrongs(answer, POS_INF, NEG_INF, NO_LIMIT, m(d), "$0$"),
        (
            f"المقام $({tex(x - c)})^2$ موجب من الجهتين ويؤول إلى $0$.",
            f"إشارة الكسر إشارة البسط ${k}$ من الجهتين، فالجهتان تتفقان.",
            f"${lim(c, 'f(x)')}=$ {answer}",
        ),
        "A",
        {"type": "infinite_side", "expr": k / (x - c) ** 2 + d, "at": c, "side": "both", "answer": answer},
    )


@variant("1.1", example=6)
def concentration_at_infinity(rng: random.Random) -> Problem:
    """نهاية عند المالانهاية لدالة نسبية في سياق تركيز مادة مع الزمن."""
    a, b, p = rng.randint(2, 12), rng.randint(1, 9), rng.randint(0, 5)
    t = sp.Symbol("t")
    concentration = (a * t + p) / (t + b)
    return Problem(
        "1.1",
        f"تركيز مادة في محلول بعد $t$ دقيقة يُعطى بالدالة $C(t)={frac(a * t + p, t + b)}$ (ملغم/لتر). "
        r"أوجد $\lim\limits_{t \to \infty} C(t)$ وفسّر الناتج.",
        m(a),
        wrongs(sp.Integer(a), sp.Rational(p, b), 0, NO_LIMIT, a + b),
        (
            "نقسم البسط والمقام على $t$.",
            rf"الحدّان $\frac{{{p}}}{{t}}$ و$\frac{{{b}}}{{t}}$ يؤولان إلى $0$، فالنهاية $\frac{{{a}}}{{1}}={a}$.",
            f"يقترب التركيز من ${a}$ ملغم/لتر مع مرور الزمن.",
        ),
        "A",
        {"type": "limit", "expr": concentration.subs(t, x), "at": sp.oo, "value": a},
    )


@variant("1.2", example=2)
def limit_rules_radical(rng: random.Random) -> Problem:
    """قواعد النهايات على كسر في مقامه جذر، ونهاية المقام لا تساوي صفرًا."""
    root = rng.randint(1, 5)
    a = rng.randint(-3, 6)
    r = root * root - a
    p, q = nz(rng, -5, 6), rng.randint(-6, 6)
    value = sp.Rational(p * a + q, root)
    radical = rf"\sqrt{{{tex(x + r)}}}"
    return Problem(
        "1.2",
        f"أوجد ${lim(a, frac(p * x + q, radical))}$.",
        m(value),
        wrongs(value, p * a + q, sp.Rational(p * a + q, root * root), NO_LIMIT, 0),
        (
            rf"نهاية المقام $\sqrt{{{a + r}}}={root}\ne 0$، فنطبّق قاعدة القسمة وقاعدة الجذر.",
            f"نهاية البسط ${tex(p * a + q)}$.",
            f"$L={frac(p * a + q, root)}={tex(value)}$",
        ),
        "K",
        {"type": "limit", "expr": (p * x + q) / sp.sqrt(x + r), "at": a, "value": value},
    )


@variant("1.2", example=5)
def limit_dne_after_cancel(rng: random.Random) -> Problem:
    """كسر يؤول بعد الاختزال إلى k/(x−c): نهايتا الجهتين لانهائيتان مختلفتان فالنهاية غير موجودة."""
    c = rng.randint(-3, 4)
    b = rng.choice([n for n in range(-4, 5) if n != c])
    k = nz(rng, -4, 4)
    top, bottom = sp.expand(k * (x - b)), sp.expand((x - c) * (x - b))
    side = rng.choice(["-", "+", "both", "both"])
    answer = NO_LIMIT if side == "both" else infinity(k if side == "+" else -k)
    at = c if side == "both" else f"{c}^{side}"
    return Problem(
        "1.2",
        f"أوجد ${lim(at, frac(top, bottom))}$.",
        answer,
        wrongs(answer, POS_INF, NEG_INF, NO_LIMIT, "$0$", m(sp.Rational(k, c - b))),
        (
            rf"${frac(top, bottom)}={frac(k, x - c)}$ حيث $x\ne {b}$.",
            f"عند ${c}$ يؤول المقام إلى $0$: من اليسار {infinity(-k)} ومن اليمين {infinity(k)}.",
            "النهايتان مختلفتان فالنهاية غير موجودة." if side == "both" else f"فالنهاية {answer}.",
        ),
        "A",
        {"type": "infinite_side", "expr": top / bottom, "at": c, "side": side, "answer": answer},
    )


@variant("1.3", example=1)
def trig_exp_substitution(rng: random.Random) -> Problem:
    """تعويض مباشر في كسر مثلثي أو أسي بعد التحقق من أن المقام لا يساوي صفرًا."""
    if rng.random() < 0.6:
        at = rng.choice([sp.pi / 6, sp.pi / 4, sp.pi / 3, sp.pi / 2, sp.pi])
        p, q = rng.randint(1, 4), rng.randint(2, 5)
        expr = (p + sp.sin(x)) / (q + sp.cos(x))
        denominator = q + sp.cos(x)
    else:
        at = sp.Integer(rng.choice([0, 0, 1]))
        p, q = rng.randint(1, 5), rng.randint(1, 4)
        expr = (sp.exp(x) + p) / (x + q)
        denominator = x + q
    value = sp.radsimp(sp.simplify(expr.subs(x, at)))
    return Problem(
        "1.3",
        f"أوجد ${lim(at, tex(expr))}$.",
        m(value),
        wrongs(value, NO_LIMIT, 0, 1, sp.Rational(p, q), p),
        (
            rf"المقام عند $x={tex(at)}$ يساوي ${tex(sp.simplify(denominator.subs(x, at)))}\ne 0$ والدالة متصلة عندها.",
            f"بالتعويض المباشر: $L={tex(value)}$",
        ),
        "K",
        {"type": "limit", "expr": expr, "at": at, "value": value},
    )


@variant("1.4", example=3)
def removable_discontinuity(rng: random.Random) -> Problem:
    """صفرا المقام: أحدهما قابل للإزالة يُعاد تعريف الدالة عنده، والآخر غير قابل."""
    a, c = rng.sample(range(-4, 5), 2)
    b = rng.choice([n for n in range(-4, 5) if n not in (a, c)])
    top, bottom = sp.expand((x - a) * (x - b)), sp.expand((x - a) * (x - c))
    value = sp.Rational(a - b, a - c)
    return Problem(
        "1.4",
        f"الدالة $f(x)={frac(top, bottom)}$ غير متصلة عند $x={a}$ و$x={c}$. "
        f"ما القيمة التي تُعطى للدالة عند $x={a}$ لتصبح متصلة عندها؟",
        m(value),
        wrongs(value, NO_LIMIT, 0, sp.Rational(a - c, a - b), 1),
        (
            rf"${frac(top, bottom)}={frac(x - b, x - c)}$ حيث $x\ne {a}$.",
            f"عند $x={a}$ عدم اتصال قابل للإزالة: ${lim(a, 'f(x)')}={tex(value)}$، فنعرّف $f({a})={tex(value)}$.",
            f"عند $x={c}$ المقام بعد الاختزال صفر والبسط لا، فعدم الاتصال غير قابل للإزالة.",
        ),
        "A",
        {"type": "removable", "expr": top / bottom, "at": a, "pole": c, "value": value},
    )


@variant("1.4", example=4)
def discontinuity_points(rng: random.Random) -> Problem:
    """نقاط عدم اتصال دالة من مجالها: أصفار المقام، والبسط متصل على الأعداد الحقيقية."""
    r1, r2 = sorted(rng.sample(range(-5, 6), 2))
    bottom = sp.expand((x - r1) * (x - r2))
    top = rng.choice([sp.exp(x), x**2 + 1, sp.sqrt(x**2 + 4)])
    answer = f"$x={r1}$ و$x={r2}$"
    return Problem(
        "1.4",
        f"حدّد نقاط عدم اتصال الدالة $f(x)={frac(top, bottom)}$.",
        answer,
        wrongs(answer, f"$x={-r2}$ و$x={-r1}$", f"$x={r1}$ فقط", "لا توجد", f"$x={r2}$ فقط"),
        (
            r"البسط متصل على $\mathbb{R}$، فعدم الاتصال عند أصفار المقام وحدها.",
            f"${tex(bottom)}={tex(sp.factor(bottom))}$",
            rf"فالدالة غير متصلة عند $x={r1}$ و$x={r2}$ ومتصلة على باقي $\mathbb{{R}}$.",
        ),
        "A",
        {"type": "discontinuities", "top": top, "bottom": bottom, "points": [r1, r2]},
    )


# الوحدة الثانية: الاشتقاق
@variant("2.1", example=1)
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


@variant("2.1", example=3)
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


@variant("2.2", example=1)
def derivative_as_limit_h(rng: random.Random) -> Problem:
    p, q, a = nz(rng, -3, 4), rng.randint(-5, 6), rng.randint(-3, 4)
    f = p * x**2 + q * x
    d = sp.diff(f, x)
    value = d.subs(x, a)
    return Problem(
        "2.2",
        rf"إذا كانت $f(x)={tex(f)}$ فما قيمة $\lim\limits_{{h \to 0}}\dfrac{{f({a}+h)-f({a})}}{{h}}$؟",
        m(value),
        wrongs(value, f.subs(x, a), 2 * p * a, 0),
        (f"هذه النهاية هي تعريف $f'({a})$.", f"$f'(x)={tex(d)}$", f"$f'({a})={tex(value)}$"),
        "K",
        {"type": "derivative", "f": f, "at": a, "value": value},
    )


@variant("2.2", example=1)
def derivative_as_limit_x(rng: random.Random) -> Problem:
    p, a = rng.randint(1, 4), nz(rng, -3, 3)
    f = p * x**3
    d = sp.diff(f, x)
    value = d.subs(x, a)
    return Problem(
        "2.2",
        rf"إذا كانت $f(x)={tex(f)}$ فما قيمة $\lim\limits_{{x \to {a}}}\dfrac{{f(x)-f({a})}}{{{tex(x - a)}}}$؟",
        m(value),
        wrongs(value, f.subs(x, a), 3 * p * a, 0),
        (f"هذه النهاية هي $f'({a})$.", f"$f'(x)={tex(d)}$", f"$f'({a})={tex(value)}$"),
        "K",
        {"type": "derivative", "f": f, "at": a, "value": value},
    )


@variant("2.3", example=2)
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


@variant("2.3", example=3)
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


@variant("2.4", example=1)
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


@variant("2.4", example=3)
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


@variant("2.5", example=2)
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


@variant("2.5", example=2)
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


@variant("2.6", example=4)
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


@variant("2.6", example=2)
def derivative_x_exponential(rng: random.Random) -> Problem:
    a, k = nz(rng, -4, 5), nz(rng, -3, 3)
    e = sp.exp(a * x)
    f, d = k * x * e, k * (1 + a * x) * e
    return Problem(
        "2.6",
        f"أوجد ${DYDX}$ إذا كانت $y={tex(f)}$.",
        m(d),
        wrongs(d, k * a * e, k * e, k * (x + a) * e, (1 + a * x) * e),
        (
            rf"قاعدة الضرب: $u={tex(k * x)},\ v={tex(e)}$",
            rf"${DYDX}={tex(k * e)}+{tex(k * x)}\cdot {tex(a * e)}={tex(d)}$",
        ),
        "A",
        {"type": "function", "f": f, "d": d, "order": 1},
    )


@variant("2.6", example=4)
def derivative_power_log(rng: random.Random) -> Problem:
    n, k = rng.randint(2, 5), nz(rng, -3, 3)
    f = k * x**n * sp.log(x)
    d = k * n * x ** (n - 1) * sp.log(x) + k * x ** (n - 1)
    return Problem(
        "2.6",
        f"أوجد ${DYDX}$ إذا كانت $y={tex(f)}$ حيث $x>0$.",
        m(d),
        wrongs(d, k * n * x ** (n - 1) / x, k * n * x ** (n - 1) * sp.log(x), k * x ** (n - 1)),
        (rf"قاعدة الضرب: $u={tex(k * x**n)},\ v=\ln x$", f"${DYDX}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 1, "positive": True},
    )


@variant("2.7", example=1)
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


@variant("2.7", example=4)
def derivative_tangent(rng: random.Random) -> Problem:
    n, k = rng.randint(2, 6), nz(rng, -4, 4)
    f, d = k * sp.tan(n * x), k * n * sp.sec(n * x) ** 2
    return Problem(
        "2.7",
        f"أوجد ${DYDX}$ إذا كانت $y={tex(f)}$.",
        m(d),
        wrongs(d, k * sp.sec(n * x) ** 2, k * n * sp.sec(n * x), -k * n * sp.csc(n * x) ** 2),
        (r"$\dfrac{d}{dx}\tan u=u'\sec^2 u$", f"${DYDX}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 1},
    )


@variant("2.7", example=5)
def derivative_x_sine(rng: random.Random) -> Problem:
    n, k = rng.randint(2, 5), nz(rng, -3, 3)
    s, c = sp.sin(n * x), sp.cos(n * x)
    f, d = k * x * s, k * s + k * n * x * c
    return Problem(
        "2.7",
        f"أوجد ${DYDX}$ إذا كانت $y={tex(f)}$.",
        m(d),
        wrongs(d, k * n * c, k * s + k * x * c, k * s - k * n * x * c),
        (rf"قاعدة الضرب: $u={tex(k * x)},\ v={tex(s)}$", f"${DYDX}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 1},
    )


@variant("2.8", example=1)
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


@variant("2.8", example=2)
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


@variant("2.9", example=2)
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


@variant("2.9", example=1)
def third_derivative_exponential(rng: random.Random) -> Problem:
    a, k = rng.choice([-3, -2, 2, 3, 4]), nz(rng, -3, 3)
    f = k * sp.exp(a * x)
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


@variant("2.9", example=3)
def second_derivative_sine(rng: random.Random) -> Problem:
    n, k = rng.randint(2, 6), nz(rng, -4, 4)
    f = k * sp.sin(n * x)
    d = -(n**2) * f
    return Problem(
        "2.9",
        rf"أوجد $\dfrac{{d^2y}}{{dx^2}}$ إذا كانت $y={tex(f)}$.",
        m(d),
        wrongs(d, -d, k * n * sp.cos(n * x), -n * f),
        (f"${DYDX}={tex(k * n * sp.cos(n * x))}$", rf"$\dfrac{{d^2y}}{{dx^2}}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 2},
    )


def tangent_line(f: sp.Expr, at: int) -> tuple[sp.Expr, sp.Expr, sp.Expr, tuple[str, ...]]:
    """الميل وقيمة الدالة والمستقيم عند نقطة، وبدائل أخطائه الشائعة (الميل مكان القيمة، العمودي، الإشارة)."""
    slope = sp.simplify(sp.diff(f, x).subs(x, at))
    point = sp.simplify(f.subs(x, at))
    line = sp.expand(slope * x + point - slope * at)
    bad = [
        sp.expand(slope * x + point),
        sp.expand(point * x + slope - point * at),
        sp.expand(-slope * x + point + slope * at),
        sp.expand(slope * x - point + slope * at),
        sp.expand(slope * x + point - slope * at + 1),
    ]
    if slope != 0:
        bad.insert(2, sp.expand(-x / slope + point + at / slope))
    return slope, point, line, wrongs(f"$y={tex(line)}$", *(f"$y={tex(b)}$" for b in bad))


def tangent_problem(lesson: str, stem: str, f: sp.Expr, at: int, first: str, level: str) -> Problem:
    slope, point, line, bad = tangent_line(f, at)
    return Problem(
        lesson,
        stem,
        f"$y={tex(line)}$",
        bad,
        (
            first,
            f"النقطة $({at},{tex(point)})$ والميل ${tex(slope)}$.",
            f"$y-{tex(point) if point >= 0 else f'({tex(point)})'}={tex(slope)}({tex(x - at)})$ أي $y={tex(line)}$",
        ),
        level,
        {"type": "tangent", "f": f, "at": at, "slope": slope, "intercept": line.subs(x, 0)},
    )


@variant("2.2", example=2)
def derivative_rational_definition(rng: random.Random) -> Problem:
    """مشتقة k/(x−c) بالتعريف: توحيد المقامين في نسبة الفارق ثم النهاية."""
    c, k = rng.randint(-5, 5), nz(rng, -6, 6)
    f, d = k / (x - c), -k / (x - c) ** 2
    shifted = f"x+h{-c:+d}" if c else "x+h"
    return Problem(
        "2.2",
        f"استعمل تعريف المشتقة لإيجاد $f'(x)$ إذا كانت $f(x)={tex(f)}$.",
        m(d),
        wrongs(d, -d, k / (x - c), sp.Integer(-k) / (x - c), -k / (x - c) ** 3),
        (
            rf"$f'(x)=\lim\limits_{{h \to 0}}\dfrac{{1}}{{h}}\left({frac(k, shifted)}-{tex(f)}\right)$",
            rf"بتوحيد المقامين: $\dfrac{{{-k}h}}{{h({shifted})({tex(x - c)})}}$، ونختصر $h$.",
            f"$f'(x)={tex(d)}$",
        ),
        "A",
        {"type": "function", "f": f, "d": d, "order": 1},
    )


@variant("2.2", example=3)
def tangent_from_known_derivative(rng: random.Random) -> Problem:
    """معادلة المماس بصيغة النقطة والميل، والمشتقة معطاة."""
    p, q, r = nz(rng, -3, 3), rng.randint(-5, 5), rng.randint(-6, 6)
    at = rng.randint(-3, 3)
    f = p * x**2 + q * x + r
    return tangent_problem(
        "2.2",
        f"إذا كانت $f(x)={tex(f)}$ ومشتقتها $f'(x)={tex(sp.diff(f, x))}$، "
        f"فأوجد معادلة المماس لمنحنى $f$ عند $x={at}$.",
        f,
        at,
        f"$f({at})={tex(f.subs(x, at))}$ و$f'({at})={tex(sp.diff(f, x).subs(x, at))}$",
        "K",
    )


@variant("2.2", example=4)
def weight_growth_rate(rng: random.Random) -> Problem:
    """معدل تغير لحظي لدالة جذرية بالتعريف والضرب في المرافق، في سياق نمو الوزن."""
    a, t0 = rng.randint(2, 9), rng.randint(1, 8)
    root = rng.randint(2, 6)
    b = root**2 - t0
    while b <= 0:
        root += 1
        b = root**2 - t0
    t = sp.Symbol("t")
    weight = a * sp.sqrt(t + b)
    value = sp.Rational(a, 2 * root)
    return Problem(
        "2.2",
        f"وزن طفل بالكيلوغرام بعد $t$ شهرًا يُعطى تقريبًا بـ $W(t)={tex(weight)}$. "
        f"أوجد معدل تغير وزنه اللحظي عند $t={t0}$.",
        m(value),
        wrongs(value, sp.Rational(a, root), sp.Rational(1, 2 * root), a * root, sp.Rational(a * root, t0)),
        (
            rf"$W'({t0})=\lim\limits_{{h \to 0}}\dfrac{{{a}\sqrt{{{root**2}+h}}-{a * root}}}{{h}}$",
            rf"نضرب في المرافق: $\dfrac{{{a}h}}{{h\left(\sqrt{{{root**2}+h}}+{root}\right)}}$، ثم $h\to 0$.",
            f"$W'({t0})={frac(a, 2 * root)}={tex(value)}$ كغ/شهر",
        ),
        "A",
        {"type": "derivative", "f": weight.subs(t, x), "at": t0, "value": value},
    )


@variant("2.3", example=1)
def derivative_of_constant(rng: random.Random) -> Problem:
    """مشتقة تعبير عددي ثابت (قوة π أو e، جذر، لوغاريتم، قوة عدد) صفر."""
    n, k = rng.randint(2, 7), rng.choice([2, 3, 5, 6, 7, 10, 11, 13])
    value, wrong = rng.choice(
        [
            (sp.pi**n, n * sp.pi ** (n - 1)),
            (sp.sqrt(k), 1 / (2 * sp.sqrt(k))),
            (sp.exp(n), n * sp.exp(n - 1)),
            (sp.log(k), sp.Rational(1, k)),
            (sp.Pow(-k, n, evaluate=False), n * (-k) ** (n - 1)),
        ]
    )
    name, var = rng.choice([("y", "x"), ("f(x)", "x"), ("s(t)", "t"), ("g(u)", "u")])
    symbol = rf"\dfrac{{d}}{{d{var}}}\left({name}\right)" if name != "y" else DYDX
    return Problem(
        "2.3",
        f"إذا كانت ${name}={tex(value)}$ فأوجد ${symbol}$.",
        "$0$",
        wrongs("$0$", wrong, value, 1),
        (f"${tex(value)}$ عدد ثابت لا يحوي ${var}$.", f"مشتقة الثابت صفر: ${symbol}=0$"),
        "K",
        {"type": "function", "f": value + 0 * x, "d": sp.Integer(0), "order": 1},
    )


@variant("2.4", example=2)
def product_root_quadratic(rng: random.Random) -> Problem:
    """قاعدة الضرب لجذر في كثير حدود تربيعي، والجذر بأس كسري."""
    a, b, c = nz(rng, -3, 4), rng.randint(-5, 5), nz(rng, -6, 6)
    x0 = rng.choice([1, 4, 9])
    v = a * x**2 + b * x + c
    f = sp.sqrt(x) * v
    value = sp.diff(f, x).subs(x, x0)
    return Problem(
        "2.4",
        rf"إذا كانت $y=\sqrt{{x}}\,({tex(v)})$ فأوجد قيمة ${DYDX}$ عند $x={x0}$.",
        m(value),
        wrongs(
            value,
            sp.diff(v, x).subs(x, x0) / (2 * sp.sqrt(x0)),
            sp.sqrt(x0) * sp.diff(v, x).subs(x, x0),
            f.subs(x, x0),
        ),
        (
            rf"$u=x^{{1/2}},\ v={tex(v)},\ u'=\dfrac{{1}}{{2}}x^{{-1/2}},\ v'={tex(sp.diff(v, x))}$",
            rf"${DYDX}=\dfrac{{{tex(v)}}}{{2\sqrt{{x}}}}+\sqrt{{x}}\,({tex(sp.diff(v, x))})$",
            f"عند $x={x0}$ القيمة ${tex(value)}$",
        ),
        "A",
        {"type": "derivative", "f": f, "at": x0, "value": value},
    )


@variant("2.4", example=5)
def tangent_to_rational(rng: random.Random) -> Problem:
    """معادلة المماس لدالة نسبية بقاعدة القسمة عند نقطة."""
    a, c, at = nz(rng, -3, 3), rng.choice([1, -1]), rng.randint(-2, 3)
    d = rng.choice([s - c * at for s in (-2, -1, 1, 2)])
    b = rng.choice([n for n in range(-4, 5) if a * d - n * c != 0])
    f = (a * x + b) / (c * x + d)
    return tangent_problem(
        "2.4",
        f"أوجد معادلة المماس لمنحنى $y={frac(a * x + b, c * x + d)}$ عند $x={at}$.",
        f,
        at,
        rf"قاعدة القسمة: ${DYDX}={frac(a * d - b * c, f'({tex(c * x + d)})^2')}$",
        "A",
    )


@variant("2.5", example=3)
def product_with_chain(rng: random.Random) -> Problem:
    """جداء عامل خطي في قوة كثير حدود: قاعدة الضرب مع السلسلة."""
    a, b = nz(rng, -3, 3), nz(rng, -4, 4)
    n, x0 = rng.randint(2, 4), rng.choice([-1, 0, 1, 2])
    inner = x**2 + b
    f = (x + a) * inner**n
    value = sp.diff(f, x).subs(x, x0)
    return Problem(
        "2.5",
        f"إذا كانت $y=({tex(x + a)})({tex(inner)})^{n}$ فأوجد قيمة ${DYDX}$ عند $x={x0}$.",
        m(value),
        wrongs(
            value,
            inner.subs(x, x0) ** n,
            n * inner.subs(x, x0) ** (n - 1) * 2 * x0,
            (x0 + a) * n * inner.subs(x, x0) ** (n - 1),
        ),
        (
            rf"${DYDX}=({tex(inner)})^{n}+({tex(x + a)})\cdot {n}({tex(inner)})^{{{n - 1}}}\cdot 2x$",
            rf"$={tex(sp.factor(sp.diff(f, x)))}$",
            f"عند $x={x0}$ القيمة ${tex(value)}$",
        ),
        "A",
        {"type": "derivative", "f": f, "at": x0, "value": value},
    )


@variant("2.5", example=4)
def velocity_root_position(rng: random.Random) -> Problem:
    """السرعة اللحظية من موضع جذري √(at²+b) بقاعدة السلسلة."""
    a, t0 = rng.randint(1, 4), rng.randint(1, 4)
    root = rng.randint(a * t0 + 1, a * t0 + 6)
    b = root**2 - a * t0**2
    t = sp.Symbol("t")
    position = sp.sqrt(a * t**2 + b)
    value = sp.Rational(a * t0, root)
    return Problem(
        "2.5",
        f"موضع جسم بالأمتار بعد $t$ ثانية هو $s(t)={tex(position)}$. أوجد سرعته اللحظية عند $t={t0}$.",
        m(value),
        wrongs(
            value,
            sp.Rational(1, 2 * root),
            sp.Rational(2 * a * t0, root),
            sp.Integer(root),
            sp.Rational(a * t0, 2 * root),
        ),
        (
            rf"$s(t)=({tex(a * t**2 + b)})^{{1/2}}$",
            rf"$v(t)=\dfrac{{1}}{{2}}({tex(a * t**2 + b)})^{{-1/2}}\cdot {2 * a}t={frac(a * t, position)}$",
            f"$v({t0})={frac(a * t0, root)}={tex(value)}$ م/ث",
        ),
        "A",
        {"type": "derivative", "f": position.subs(t, x), "at": t0, "value": value},
    )


@variant("2.6", example=3)
def exponential_decay_rate(rng: random.Random) -> Problem:
    """معدل التغير اللحظي لنموذج أسي متناقص A·e^(−kt) عند زمن معطى."""
    k = rng.choice([sp.Rational(1, 2), sp.Rational(1, 4), sp.Rational(1, 5), sp.Rational(1, 10)])
    amount = rng.choice([40, 60, 80, 100, 200, 500])
    t0 = int(rng.randint(1, 3) / k)
    t = sp.Symbol("t")
    model = amount * sp.exp(-k * t)
    value = -k * amount * sp.exp(-k * t0)
    return Problem(
        "2.6",
        f"كمية دواء في الدم (ملغم) بعد $t$ ساعة هي $Q(t)={tex(model)}$. أوجد معدل تغير الكمية عند $t={t0}$.",
        m(value),
        wrongs(value, -value, model.subs(t, t0), -amount * sp.exp(-k * t0), -k * amount),
        (
            f"$Q'(t)={tex(sp.diff(model, t))}$",
            rf"$Q'({t0})={tex(value)}\approx {float(value):.2f}$ ملغم/ساعة، والإشارة السالبة تعني التناقص.",
        ),
        "A",
        {"type": "derivative", "f": model.subs(t, x), "at": t0, "value": value},
    )


@variant("2.7", example=2)
def derivative_cosine_forms(rng: random.Random) -> Problem:
    """مشتقة cos لزاوية خطية أو قوة لـ cos بقاعدة السلسلة."""
    a, b, k = nz(rng, -5, 5), rng.randint(-4, 4), nz(rng, -3, 3)
    if rng.random() < 0.5:
        f = k * sp.cos(a * x + b)
        d = -k * a * sp.sin(a * x + b)
        others = (k * a * sp.sin(a * x + b), -k * sp.sin(a * x + b), -k * a * sp.cos(a * x + b))
        step = rf"$u={tex(a * x + b)}$ و$u'={a}$، و$\dfrac{{d}}{{dx}}\cos u=-u'\sin u$"
    else:
        n, a = rng.randint(2, 5), abs(a)
        f = k * sp.cos(a * x) ** n
        d = -k * n * a * sp.cos(a * x) ** (n - 1) * sp.sin(a * x)
        others = (-d, -k * n * sp.cos(a * x) ** (n - 1) * sp.sin(a * x), k * n * a * sp.sin(a * x) ** (n - 1))
        step = rf"قاعدة السلسلة للقوة: ${n}\cos^{{{n - 1}}}({tex(a * x)})\cdot(-{a}\sin({tex(a * x)}))$"
    return Problem(
        "2.7",
        f"أوجد ${DYDX}$ إذا كانت $y={tex(f)}$.",
        m(d),
        wrongs(d, *others),
        (step, f"${DYDX}={tex(d)}$"),
        "A",
        {"type": "function", "f": f, "d": d, "order": 1},
    )


@variant("2.7", example=3)
def velocity_cosine_position(rng: random.Random) -> Problem:
    """سرعة لحظية من موضع k·cos(t²+c) بالراديان عند زمن معطى."""
    k, c, t0 = nz(rng, -4, 4), rng.randint(0, 4), rng.randint(1, 3)
    t = sp.Symbol("t")
    position = k * sp.cos(t**2 + c)
    value = -2 * k * t0 * sp.sin(t0**2 + c)
    return Problem(
        "2.7",
        f"موضع جسم بالسنتيمتر بعد $t$ ثانية هو $s(t)={tex(position)}$ (الزاوية بالراديان). "
        f"أوجد سرعته اللحظية عند $t={t0}$.",
        m(value),
        wrongs(
            value,
            -value,
            -k * sp.sin(t0**2 + c),
            -2 * k * t0 * sp.cos(t0**2 + c),
            position.subs(t, t0),
        ),
        (
            f"$v(t)=s'(t)={tex(sp.diff(position, t))}$",
            rf"$v({t0})={tex(value)}\approx {float(value):.2f}$ سم/ث",
        ),
        "A",
        {"type": "derivative", "f": position.subs(t, x), "at": t0, "value": value},
    )


@variant("2.8", example=3)
def implicit_with_roots(rng: random.Random) -> Problem:
    """اشتقاق ضمني لعلاقة فيها √x وx√y وy² عند نقطة: الضرب والسلسلة والقوى الكسرية."""
    while True:
        p, q = rng.choice([1, 4, 9]), rng.choice([1, 4, 9])
        a = nz(rng, -2, 2)
        F_y = sp.Rational(p, 2 * sp.sqrt(q)) - 2 * a * q  # ∂F/∂y عند النقطة
        if F_y != 0:
            break
    c = sp.sqrt(p) + p * sp.sqrt(q) - a * q**2
    relation = sp.sqrt(x) + x * sp.sqrt(y) - a * y**2
    F_x = sp.Rational(1, 2 * sp.sqrt(p)) + sp.sqrt(q)
    value = -F_x / F_y
    coefficient = f"{-a:+d}" if abs(a) != 1 else ("-" if a > 0 else "+")
    shown = rf"\sqrt{{x}}+x\sqrt{{y}}{coefficient}y^2"
    return Problem(
        "2.8",
        f"أوجد ${DYDX}$ عند النقطة $({p},{q})$ على المنحنى ${shown}={tex(c)}$.",
        m(value),
        wrongs(value, -value, -F_y / F_x, -F_x, F_x / (2 * a * q)),
        (
            rf"$\dfrac{{1}}{{2\sqrt{{x}}}}+\sqrt{{y}}+\dfrac{{x}}{{2\sqrt{{y}}}}y'{-2 * a:+d}y\,y'=0$",
            rf"$y'=-\dfrac{{\frac{{1}}{{2\sqrt{{x}}}}+\sqrt{{y}}}}{{\frac{{x}}{{2\sqrt{{y}}}}{-2 * a:+d}y}}$",
            f"عند $({p},{q})$: $y'={tex(value)}$",
        ),
        "R",
        {"type": "implicit", "F": relation - c, "point": (p, q), "value": value},
    )


@variant("2.9", example=4)
def implicit_second_derivative(rng: random.Random) -> Problem:
    """y'' من علاقة ضمنية ax³+y²=c عند نقطة، بالتعويض عن y'."""
    a, p, q = rng.randint(1, 3), rng.randint(-2, 3), nz(rng, -4, 4)
    c = a * p**3 + q**2
    F = a * x**3 + y**2 - c
    first = sp.idiff(F, y, x)
    second = sp.simplify(sp.idiff(F, y, x, 2))
    at = {x: p, y: q}
    value = sp.nsimplify(second.subs(at))
    return Problem(
        "2.9",
        rf"إذا كانت ${tex(a * x**3 + y**2)}={c}$ فأوجد $\dfrac{{d^2y}}{{dx^2}}$ عند النقطة $({p},{q})$.",
        m(value),
        wrongs(value, first.subs(at), -value, sp.diff(-a * x**3, x, 2).subs(x, p) / (2 * q)),
        (
            f"$y'={tex(first)}$",
            f"نشتق مرة ثانية بقاعدة القسمة ونعوّض عن $y'$: $y''={tex(second)}$",
            f"عند $({p},{q})$: $y''={tex(value)}$",
        ),
        "R",
        {"type": "implicit_second", "F": F, "point": (p, q), "value": value},
    )


# الوحدة الثالثة: تطبيقات الاشتقاق
@variant("3.1", example=2)
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


@variant("3.2", example=2)
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


@variant("3.2", example=5)
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


@variant("3.3", example=3)
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


@variant("3.3", example=3)
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


@variant("3.3", example=3)
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


NONE_FOUND = "لا توجد"
EXTREMUM_WORDS = {"max": "عظمى محلية عند", "min": "صغرى محلية عند", "none": "لا قيمة قصوى عند"}


def sign_change(left: float, right: float) -> str:
    """نوع النقطة الحرجة من إشارة المشتقة قبلها وبعدها (اختبار المشتقة الأولى)."""
    if left > 0 > right:
        return "max"
    if left < 0 < right:
        return "min"
    return "none"


def extrema_text(points: list[tuple[int, str]]) -> str:
    return "، و".join(f"{EXTREMUM_WORDS[kind]} $x={p}$" for p, kind in points)


def extrema_problem(
    lesson: str,
    stem: str,
    f: sp.Expr,
    points: list[tuple[int, str]],
    steps: tuple[str, ...],
    rng: random.Random,
) -> Problem:
    """تصنيف النقاط الحرجة، وبدائله تصنيفات أخرى للنقاط نفسها: العكس أولًا ثم غيره."""
    answer = extrema_text(points)
    truth = tuple(kind for _, kind in points)
    swapped = tuple({"max": "min", "min": "max", "none": "none"}[k] for k in truth)
    others = [t for t in product(EXTREMUM_WORDS, repeat=len(points)) if t not in (truth, swapped)]
    rng.shuffle(others)
    texts = [extrema_text(list(zip([p for p, _ in points], t, strict=True))) for t in [swapped, *others]]
    return Problem(
        lesson,
        stem,
        answer,
        wrongs(answer, *texts[:6]),
        (*steps, f"إذن: {answer}."),
        "R",
        {"type": "extrema", "f": f, "points": points},
    )


def cube_root_text(inner: sp.Expr, power: int = 1) -> str:
    body = tex(inner) if power == 1 else f"({tex(inner)})^{power}" if inner != x else f"x^{power}"
    return rf"\sqrt[3]{{{body}}}"


def coefficient(k: int) -> str:
    return {1: "", -1: "-"}.get(k, str(k))


@variant("3.1", example=3)
def critical_where_derivative_undefined(rng: random.Random) -> Problem:
    """قيمة حرجة لا تكون فيها المشتقة صفرًا بل غير موجودة: قوة كسرية 2/3."""
    c, k, d = rng.randint(-3, 3), nz(rng, -3, 3), rng.randint(-4, 4)
    f = k * sp.Abs(x - c) ** sp.Rational(2, 3) + d
    shown = coefficient(k) + cube_root_text(x - c, 2) + (f"{d:+d}" if d else "")
    falling, rising = rf"$(-\infty,{c})$", rf"$({c},\infty)$"
    if k < 0:
        falling, rising = rising, falling
    return Problem(
        "3.1",
        f"أوجد القيم الحرجة للدالة $f(x)={shown}$.",
        f"$x={c}$",
        wrongs(f"$x={c}$", NONE_FOUND, f"$x={-c}$", "$x=0$", f"$x={c + 1}$", f"$x={d}$", f"$x={c - 1}$", f"$x={c + 2}$"),
        (
            rf"$f(x)={coefficient(k)}({tex(x - c)})^{{2/3}}{f'{d:+d}' if d else ''}$، "
            rf"فـ $f'(x)={frac(2 * k, '3' + cube_root_text(x - c))}$",
            f"البسط لا يساوي صفرًا فلا تنعدم المشتقة، لكنها غير موجودة عند $x={c}$ والدالة معرفة عندها.",
            f"القيمة الحرجة $x={c}$، والدالة متناقصة على {falling} ومتزايدة على {rising}.",
        ),
        "A",
        {"type": "critical_dne", "f": f, "at": c},
    )


@variant("3.1", example=4)
def rational_without_critical_values(rng: random.Random) -> Problem:
    """دالة كسرية بلا قيم حرجة: تتزايد (أو تتناقص) على فترتين منفصلتين تفصلهما نقطة خارج المجال."""
    c, a = rng.randint(-3, 3), nz(rng, -3, 3)
    b = rng.choice([n for n in range(-5, 6) if -a * c - n != 0])
    f = (a * x + b) / (x - c)
    top = -a * c - b
    ask_up = rng.choice([True, False])
    both = rf"$(-\infty,{c})$ و$({c},\infty)$"
    answer = both if (top > 0) == ask_up else NONE_FOUND
    word = "تزايد" if ask_up else "تناقص"
    return Problem(
        "3.1",
        f"حدد فترات {word} الدالة $f(x)={frac(a * x + b, x - c)}$.",
        answer,
        wrongs(
            answer, both, NONE_FOUND, r"$(-\infty,\infty)$", rf"$(-\infty,{c})$ فقط", rf"$({c},\infty)$ فقط"
        ),
        (
            rf"قاعدة القسمة: $f'(x)={frac(top, f'({tex(x - c)})^2')}$",
            f"البسط ثابت لا يساوي صفرًا فلا قيم حرجة، و$x={c}$ خارج المجال.",
            f"إشارة $f'$ إشارة ${top}$ على المجال كله، فالدالة {'متزايدة' if top > 0 else 'متناقصة'} على كل من "
            f"$(-\\infty,{c})$ و$({c},\\infty)$؛ فترات ال{word}: {answer}",
        ),
        "A",
        {"type": "monotone_pieces", "f": f, "pole": c, "ask_up": ask_up, "answer": answer},
    )


@variant("3.2", example=3)
def extrema_with_cusp(rng: random.Random) -> Problem:
    """قيم قصوى محلية لدالة بقوة 2/3: نقطة حرجة تنعدم فيها المشتقة وأخرى (رأس حاد) لا توجد فيها."""
    c, n, k = rng.randint(-2, 2), nz(rng, -2, 2), rng.choice([-2, -1, 1, 2])
    t = x - c
    f = k * sp.Abs(t) ** sp.Rational(2, 3) * (t - 5 * n)

    def slope_sign(v: float) -> float:
        return k * (5 * v - 10 * n) * (1 if v > 0 else -1)

    points = sorted(
        [
            (c, sign_change(slope_sign(-0.5), slope_sign(0.5))),
            (c + 2 * n, sign_change(slope_sign(2 * n - 0.5), slope_sign(2 * n + 0.5))),
        ]
    )
    power = "x^{2/3}" if c == 0 else f"({tex(t)})^{{2/3}}"
    return extrema_problem(
        "3.2",
        f"أوجد القيم القصوى المحلية للدالة $f(x)={coefficient(k)}{power}({tex(t - 5 * n)})$ وصنّفها.",
        f,
        points,
        (
            f"$f'(x)={frac(sp.expand(k * (5 * t - 10 * n)), '3' + cube_root_text(t))}$",
            f"$f'=0$ عند $x={c + 2 * n}$، و$f'$ غير موجودة عند $x={c}$ والدالة معرفة عندها: قيمتان حرجتان.",
            "اختبار المشتقة الأولى بنقاط اختبار على خط الأعداد.",
        ),
        rng,
    )


@variant("3.2", example=4)
def extrema_power_exponential(rng: random.Random) -> Problem:
    """قيم قصوى لـ k·xⁿ·e^(ax): إحدى القيمتين الحرجتين ليست قصوى حين يتكرر العامل x."""
    n = rng.choice([2, 3])
    a, k = rng.choice([-n, -1, 1, n]), rng.choice([-2, -1, 1, 2])
    f = k * x**n * sp.exp(a * x)
    other = sp.Integer(-n) / a

    def slope_sign(v: float) -> float:
        return k * v ** (n - 1) * (n + a * v)

    points = sorted(
        (int(p), sign_change(slope_sign(float(p) - 0.5), slope_sign(float(p) + 0.5))) for p in (0, other)
    )
    return extrema_problem(
        "3.2",
        f"أوجد القيم القصوى المحلية للدالة $f(x)={tex(f)}$ وصنّفها.",
        f,
        points,
        (
            f"$f'(x)={tex(sp.factor(sp.diff(f, x)))}$",
            f"$e^{{{tex(a * x)}}}>0$، فالقيمتان الحرجتان $x=0$ و$x={tex(other)}$.",
            "اختبار المشتقة الأولى: الإشارة لا تتغير عند عامل مكرر بقوة زوجية.",
        ),
        rng,
    )


@variant("3.2", example=6)
def absolute_extrema_quartic(rng: random.Random) -> Problem:
    """قيم قصوى مطلقة لكثيرة حدود رباعية على ℝ: توجد واحدة فقط بحسب إشارة المعامل الرئيس."""
    p, q = rng.choice([(p, q) for p in range(-3, 4) for q in range(p + 1, 4) if p and q and (p + q) % 3 == 0])
    s, d = rng.choice([1, -1]), rng.randint(-5, 5)
    f = s * (x**4 - sp.Rational(4 * (p + q), 3) * x**3 + 2 * p * q * x**2) + d
    values = {point: f.subs(x, point) for point in sorted((0, p, q))}
    want_max = rng.choice([True, False])
    exists = want_max == (s < 0)
    best = (max if want_max else min)(values.values())
    answer = m(best) if exists else NONE_FOUND
    word = "العظمى" if want_max else "الصغرى"
    table = "، ".join(f"$f({point})={tex(val)}$" for point, val in values.items())
    ends = "+\\infty" if s > 0 else "-\\infty"
    return Problem(
        "3.2",
        f"أوجد القيمة {word} المطلقة للدالة $f(x)={tex(f)}$ على مجموعة الأعداد الحقيقية إن وُجدت.",
        answer,
        wrongs(answer, NONE_FOUND, *(m(v) for v in values.values()), m(-best), m(best + 1), m(best - 1)),
        (
            f"$f'(x)={tex(sp.factor(sp.diff(f, x)))}$، والقيم الحرجة $x=0$ و$x={p}$ و$x={q}$.",
            f"جدول القيم: {table}",
            f"$f(x)\\to {ends}$ عند الطرفين، فالقيمة {word} المطلقة {answer if exists else 'غير موجودة'}.",
        ),
        "R",
        {
            "type": "absolute_line",
            "f": f,
            "max": want_max,
            "answer": answer,
            "value": best if exists else None,
        },
    )


def intervals_tex(intervals: list[tuple[sp.Expr, sp.Expr]]) -> str:
    if not intervals:
        return NONE_FOUND
    return "$" + r"\cup".join(rf"\left({tex(a)},{tex(b)}\right)" for a, b in intervals) + "$"


@variant("3.3", example=1)
def concavity_quadratic_or_trig(rng: random.Random) -> Problem:
    """فترات التقعر: تربيعية مشتقتها الثانية ثابتة، أو دالة مثلثية على (0، 2π) بأصفار f''."""
    up = rng.choice([True, False])
    word = "لأعلى" if up else "لأسفل"
    if rng.random() < 0.35:
        a, b, c = nz(rng, -3, 3), rng.randint(-5, 5), rng.randint(-5, 5)
        f = a * x**2 + b * x + c
        domain, region = (-sp.oo, sp.oo), ""
        chosen = [domain] if (a > 0) == up else []
        other = [] if chosen else [domain]
    else:
        k, b = nz(rng, -3, 3), rng.randint(-2, 2)
        trig = rng.choice([sp.sin, sp.cos])
        f = k * trig(x) + b * x
        domain, region = (sp.Integer(0), 2 * sp.pi), r" على الفترة $(0,2\pi)$"
        pi = sp.pi
        if trig is sp.sin:  # f''=−k·sin x
            positive = [(pi, 2 * pi)] if k > 0 else [(sp.Integer(0), pi)]
            negative = [(sp.Integer(0), pi)] if k > 0 else [(pi, 2 * pi)]
        else:  # f''=−k·cos x
            middle, outer = [(pi / 2, 3 * pi / 2)], [(sp.Integer(0), pi / 2), (3 * pi / 2, 2 * pi)]
            positive, negative = (middle, outer) if k > 0 else (outer, middle)
        chosen, other = (positive, negative) if up else (negative, positive)
    answer = intervals_tex(chosen)
    return Problem(
        "3.3",
        f"حدد الفترات التي يكون فيها منحنى $f(x)={tex(f)}$ مقعرًا {word}{region}.",
        answer,
        wrongs(
            answer,
            intervals_tex(other),
            intervals_tex([domain]),
            NONE_FOUND,
            r"$\left(0,\pi\right)$",
            intervals_tex([(sp.Integer(0), sp.oo)]),
        ),
        (
            f"$f''(x)={tex(sp.diff(f, x, 2))}$",
            "نحل $f''(x)=0$ ونختبر الإشارة على خط الأعداد بين أصفارها."
            if region
            else "المشتقة الثانية ثابتة فإشارتها واحدة على المجال كله.",
            f"المنحنى مقعر {word} حيث $f''{'>' if up else '<'}0$: {answer}",
        ),
        "A",
        {
            "type": "concave_set",
            "f": f,
            "up": up,
            "intervals": chosen,
            "domain": (-10, 10) if region == "" else domain,
        },
    )


@variant("3.3", example=2)
def gaussian_inflection(rng: random.Random) -> Problem:
    """نقطتا انعطاف دالة أسية غاوسية k·e^(−(x−c)²/(2r²)) عند c±r."""
    r, c, k = rng.randint(1, 3), rng.randint(-2, 2), rng.randint(1, 5)
    f = k * sp.exp(-((x - c) ** 2) / (2 * r**2))
    height = k * sp.exp(sp.Rational(-1, 2))
    answer = f"$({c - r},{tex(height)})$ و$({c + r},{tex(height)})$"
    return Problem(
        "3.3",
        f"أوجد نقاط انعطاف منحنى الدالة $f(x)={tex(f)}$.",
        answer,
        wrongs(
            answer,
            f"$({c},{k})$",
            f"$({c - r},{k})$ و$({c + r},{k})$",
            f"$({c - 2 * r},{tex(k * sp.exp(-2))})$ و$({c + 2 * r},{tex(k * sp.exp(-2))})$",
            f"$({c - r},{tex(height)})$ فقط",
        ),
        (
            f"$f'(x)={tex(sp.factor(sp.diff(f, x)))}$",
            f"$f''(x)={tex(sp.factor(sp.diff(f, x, 2)))}$",
            f"الأسية موجبة، فـ $f''=0$ عند $({tex(x - c)})^2={r * r}$ أي $x={c - r}$ و$x={c + r}$، وتتغير الإشارة عندهما.",
            f"نقطتا الانعطاف {answer}",
        ),
        "A",
        {"type": "inflections", "f": f, "points": [(c - r, height), (c + r, height)], "around": c},
    )


@variant("3.3", example=4)
def second_derivative_test(rng: random.Random) -> Problem:
    """اختبار المشتقة الثانية: تكعيبية بنقطتين، أو خماسية يفشل فيها الاختبار عند 0 فنرجع للمشتقة الأولى."""
    if rng.random() < 0.5:
        f, p, q, _sign = cubic_with_critical_points(rng)
        second = sp.diff(f, x, 2)
        points = [
            (p, "max" if second.subs(x, p) < 0 else "min"),
            (q, "max" if second.subs(x, q) < 0 else "min"),
        ]
        steps = (
            f"$f'(x)={tex(sp.factor(sp.diff(f, x)))}$، والقيم الحرجة $x={p}$ و$x={q}$.",
            f"$f''(x)={tex(second)}$: $f''({p})={tex(second.subs(x, p))}$ و$f''({q})={tex(second.subs(x, q))}$.",
            "المشتقة الثانية السالبة تعني قيمة عظمى محلية، والموجبة صغرى.",
        )
    else:
        a, k = rng.choice([1, 2]), rng.choice([-2, -1, 1, 2])
        f = k * (3 * x**5 - 5 * a**2 * x**3)
        second = sp.diff(f, x, 2)
        points = [(-a, "max" if k > 0 else "min"), (0, "none"), (a, "min" if k > 0 else "max")]
        steps = (
            f"$f'(x)={tex(sp.factor(sp.diff(f, x)))}$، والقيم الحرجة $x={-a}$ و$x=0$ و$x={a}$.",
            f"$f''(x)={tex(second)}$: $f''({-a})={tex(second.subs(x, -a))}$ و$f''(0)=0$ و$f''({a})={tex(second.subs(x, a))}$.",
            "عند $x=0$ يفشل اختبار المشتقة الثانية، فنستعمل الأولى: العامل $x^2$ لا يغيّر إشارتها هناك.",
        )
    return extrema_problem(
        "3.3",
        f"استعمل اختبار المشتقة الثانية لإيجاد القيم القصوى المحلية للدالة $f(x)={tex(f)}$.",
        f,
        points,
        steps,
        rng,
    )


def with_unit(value: Any, unit: str) -> str:
    return f"${tex(value)}$ {unit}"


@variant("3.5", example=1)
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


def box_sheets() -> list[tuple[int, int, int]]:
    """أبعاد صفيحة (a≤b) يكون فيها القصّ الأمثل x صحيحًا: x = (a+b-√(a²-ab+b²))/6 من V'=0."""
    found = []
    for a in range(6, 61):
        for b in range(a, 61):
            disc = a * a - a * b + b * b
            r = sp.sqrt(disc)
            if r.is_integer and (a + b - int(r)) % 6 == 0:
                cut = (a + b - int(r)) // 6
                if 0 < cut < a / 2:
                    found.append((a, b, cut))
    return found


BOX_SHEETS = box_sheets()


@variant("3.5", example=2)
def open_box(rng: random.Random) -> Problem:
    a, b, n = rng.choice(BOX_SHEETS)
    volume = x * (a - 2 * x) * (b - 2 * x)
    value = volume.subs(x, n)
    unit = "سنتيمترًا مكعبًا"
    answer = with_unit(value, unit)
    others = (2 * n, sp.Rational(n, 2), sp.Rational(3 * n, 2))
    sheet = (
        f"صفيحة مربعة طول ضلعها ${a}$ سنتيمترًا" if a == b else f"صفيحة مستطيلة أبعادها ${a}$ و${b}$ سنتيمترًا"
    )
    return Problem(
        "3.5",
        f"{sheet}، قُصّ من كل ركن منها مربع طول ضلعه $x$ ثم ثُنيت الجوانب لعمل صندوق مفتوح. "
        "أوجد أكبر حجم ممكن للصندوق.",
        answer,
        wrongs(answer, *[with_unit(volume.subs(x, v), unit) for v in others]),
        (
            f"$V(x)=x({tex(a - 2 * x)})({tex(b - 2 * x)})$ حيث $0<x<{tex(sp.Rational(a, 2))}$.",
            f"$V'(x)={tex(sp.expand(sp.diff(volume, x)))}=0$ داخل المجال عند $x={n}$.",
            f"أكبر حجم {answer}.",
        ),
        "R",
        {
            "type": "optimum",
            "f": volume,
            "low": 0,
            "high": sp.Rational(a, 2),
            "arg": n,
            "value": value,
            "max": True,
        },
    )


@variant("3.5", example=1)
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


# مولّدات الرسوم والمستويات ومقرر العاشر في وحدات مستقلة تسجّل نفسها في REGISTRY عند الاستيراد.
from . import graph_problems, level_problems, sketch_problems  # noqa: E402, F401, I001
from . import grade10_problems  # noqa: E402, F401, I001
