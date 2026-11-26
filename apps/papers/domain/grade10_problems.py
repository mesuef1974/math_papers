"""مولّدات العاشر، الفصل الأول (المقرر g10-s1): مسائل أصلية من مهارة الدرس بلغته، بلا نص من الكتاب.

كل صيغة تصرّح برقم مثال الكتاب الذي تقيس مهارته (example)، فيمنع اختبار النطاق بناء سؤال على مثال إثرائي.
البناء عكسي كما في generators.py: الرأس والمعاملات تُختار أولًا ثم تُشتق منها قاعدة الدالة بأعداد صحيحة.

الوحدة 1، الدوال التربيعية: 1.1 الدالة الرئيسة f(x)=ax²، 1.2 صيغة الرأس، 1.3 الصيغة القياسية.
الوحدة 2 (أ)، حل المعادلات التربيعية: 2.1 بالتمثيل البياني والجداول، 2.2 بالتحليل إلى العوامل، 2.3 المقادير
الجذرية، 2.5 إكمال المربع، 2.6 القانون العام والمميز.
الوحدة 2 (ب): 2.7 المعادلات النسبية، 2.8 الأنظمة الخطية-التربيعية، 2.9 المتباينات التربيعية، 2.10 معادلة
الدائرة.
الوحدة 3: 3.3 تشابه المثلثات، 3.4 تشابه المثلثات القائمة والمتوسط الهندسي، 3.5 المستقيمات المتوازية وتناسب الأضلاع.
"""

from __future__ import annotations

import itertools
import math
import random
from collections.abc import Callable, Sequence
from typing import Any

import sympy as sp

from apps.curriculum.courses import GRADE10_SLUG

from .generators import (
    ERROR_SPOTTING,
    ErrorSpotting,
    Problem,
    frac,
    m,
    minus,
    nz,
    tagged_wrongs,
    tex,
    variant,
    with_unit,
    x,
    y,
)

G10 = GRADE10_SLUG
UP, DOWN = "الأعلى", "الأسفل"
RIGHT, LEFT = "اليمين", "اليسار"
HALF = sp.Rational(1, 2)
# معاملات تغيّر اتساع القطع المكافئ: لا واحد فيها، فكل قيمة أضيق أو أوسع من الدالة الرئيسة.
SCALES = (
    sp.Rational(1, 4),
    sp.Rational(1, 3),
    HALF,
    sp.Rational(2, 3),
    sp.Rational(3, 4),
    sp.Rational(3, 2),
    2,
    sp.Rational(5, 2),
    3,
    4,
    5,
)
INTEGER_SCALES = (-3, -2, -1, 1, 2, 3)


def lead(a: Any) -> str:
    """المعامل قبل x² أو قبل القوس: يُحذف الواحد وتبقى إشارته."""
    return {1: "", -1: "-"}.get(a, tex(a))


def signed(n: int) -> str:
    """حدّ ثابت بإشارته في آخر العبارة، ويُحذف الصفر."""
    return f"{n:+d}" if n else ""


def shifted(h: int) -> str:
    return "x" if h == 0 else f"(x{-h:+d})"


def ax2(a: Any) -> str:
    return f"{lead(a)}x^2"


def vertex_form(a: Any, h: int, k: int) -> str:
    """a(x-h)²+k نصًّا بترتيب صيغة الرأس (sympy يعيد ترتيب الحدود فيضيع شكل الصيغة)."""
    return f"{lead(a)}{shifted(h)}^2{signed(k)}"


def units(n: int) -> str:
    """عدد وحدات الإزاحة بصيغته العربية."""
    return {1: "وحدة واحدة", 2: "وحدتين"}.get(n, f"${n}$ وحدات")


def sign_word(a: Any) -> str:
    return "موجب" if a > 0 else "سالب"


def opening(a: Any) -> str:
    return UP if a > 0 else DOWN


def scale(rng: random.Random) -> Any:
    return rng.choice(SCALES) * rng.choice([1, -1])


def standard_from_vertex(a: int, h: int, k: int) -> tuple[sp.Expr, int, int]:
    """(الدالة في الصيغة القياسية، b، c) لقطع مكافئ رأسه (h,k)."""
    b, c = -2 * a * h, a * h * h + k
    return a * x**2 + b * x + c, b, c


def axis_step(a: int, b: int, h: int) -> str:
    return f"$x=-\\dfrac{{b}}{{2a}}=-\\dfrac{{{b}}}{{2({a})}}={h}$"


def value_step(a: int, b: int, c: int, h: int, k: int) -> str:
    return f"$f({h})={lead(a)}({h})^2{b:+d}({h}){signed(c)}={k}$"


# «اكتشف الخطأ» في حل حسابي: كل خطوة قيم تُحسب بقاعدة (عبارات sympy) من قيم الخطوات التي قبلها.
SPOT_TASK = (
    "في الخطوات المرقّمة الآتية، فأخطأ في خطوة واحدة وبنى عليها ما بعدها. حدّد رقم الخطوة الخاطئة، ثم صحّحها."
)
Rule = tuple[Any, ...]
Row = tuple[Any, ...]


def ref(step: int, part: int = 0) -> sp.Symbol:
    """قيمة من خطوة سابقة (رقمها من 1) داخل قاعدة خطوة لاحقة."""
    return sp.Symbol(f"s{step}_{part}")


def value_chain(rules: Sequence[Rule], slip: tuple[int, Rule] | None = None) -> list[Row] | None:
    """قيم الخطوات بالتتابع؛ slip (رقم خطوة، قاعدة خاطئة) تُزرع فيها وتُبنى عليها الخطوات التالية بقواعدها.

    يعيد None إن خرجت قيمة غير نسبية (قسمة على صفر بعد الزلّة).
    """
    rows: list[Row] = []
    for n, rule in enumerate(rules, 1):
        used = slip[1] if slip is not None and slip[0] == n else rule
        known = {ref(i, j): value for i, row in enumerate(rows, 1) for j, value in enumerate(row)}
        row = tuple(sp.sympify(expr).subs(known) for expr in used)
        if not all(value.is_rational for value in row):
            return None
        rows.append(row)
    return rows


def spotted_values(
    lesson: str,
    stem: str,
    rules: Sequence[Rule],
    slip: tuple[int, str, Rule],
    texts: Callable[[list[Row], bool], tuple[str, ...]],
    answer: str,
    given: dict[str, Any],
) -> ErrorSpotting | None:
    """مسألة «اكتشف الخطأ» من سلسلة قيم: slip (رقم الخطوة، نوع الخطأ، قاعدتها الخاطئة).

    texts يكتب الخطوات من قيمها (والعلم: هل هي المعروضة بزلّتها). يعيد None إن لم تغيّر الزلّة الجواب.
    """
    step, kind, wrong = slip
    solved, shown = value_chain(rules), value_chain(rules, (step, wrong))
    if solved is None or shown is None or shown[-1] == solved[-1]:
        return None
    return ErrorSpotting(
        lesson,
        stem,
        texts(shown, True),
        step,
        kind,
        texts(solved, False)[step - 1],
        answer,
        "R",
        {
            "type": "error_spotting_values",
            **given,
            "steps": tuple(shown),
            "rules": tuple(rules),
            "fixed": solved[step - 1],
        },
    )


Chain = list[tuple[str, sp.Expr]]


def spotted_chain(
    lesson: str,
    stem: str,
    chains: tuple[Chain, Chain],
    slip: tuple[int, str],
    answer: str,
    given: sp.Expr,
    roots: tuple[Any, ...],
) -> ErrorSpotting:
    """مسألة «اكتشف الخطأ» من سلسلتي معادلات (المعروضة بزلّتها، ثم الصحيحة): كل خطوة نصها ومعادلتها (عبارة = 0).

    slip (رقم الخطوة، نوع الخطأ)؛ given المعادلة المعطاة في صيغتها القياسية، وroots حلولها.
    """
    shown, solved = chains
    step, kind = slip
    return ErrorSpotting(
        lesson,
        stem,
        tuple(text for text, _ in shown),
        step,
        kind,
        solved[step - 1][0],
        answer,
        "R",
        {
            "type": "error_spotting",
            "given": given,
            "steps": tuple(equation for _, equation in shown),
            "fixed": solved[step - 1][1],
            "roots": roots,
        },
    )


def exact(value: Any) -> str:
    """عدد نسبي: صحيح كما هو، وكسر بإشارته أمامه."""
    value = sp.Rational(value)
    if value.q == 1:
        return str(value.p)
    return f"{'-' if value < 0 else ''}\\dfrac{{{abs(value.p)}}}{{{value.q}}}"


def quotient(top: Any, bottom: Any) -> str:
    """الكسر كما كُتب ثم قيمته المبسّطة إن خالفته."""
    shown, value = frac(top, bottom), exact(sp.Rational(top, bottom))
    return shown if shown == value else f"{shown}={value}"


# الدرس 1.1: المميزات الأساسية للدالة التربيعية f(x)=ax²
@variant("1.1", G10, example=2)
def parabola_opening_and_width(rng: random.Random) -> Problem:
    a = scale(rng)

    def describe(up: bool, narrow: bool) -> str:
        return (
            f"يفتح إلى {UP if up else DOWN}، وهو {'أضيق' if narrow else 'أوسع'} من التمثيل البياني للدالة $g$"
        )

    up, narrow = bool(a > 0), bool(abs(a) > 1)
    answer = describe(up, narrow)
    wrong, kinds = tagged_wrongs(
        answer,
        ("partial", describe(up, not narrow)),
        ("partial", describe(not up, narrow)),
        ("direction", describe(not up, not narrow)),
    )
    return Problem(
        "1.1",
        f"صف اتجاه فتحة التمثيل البياني للدالة $f(x)={ax2(a)}$ واتساعه مقارنةً بالتمثيل البياني "
        "للدالة التربيعية الرئيسة $g(x)=x^2$.",
        answer,
        wrong,
        (
            f"$a={tex(a)}$ {sign_word(a)}، فالقطع المكافئ يفتح إلى {opening(a)}.",
            f"$|a|={tex(abs(a))}$ {'أكبر' if narrow else 'أصغر'} من $1$، فالتمثيل البياني "
            f"{'أضيق' if narrow else 'أوسع'} من التمثيل البياني للدالة $g$.",
        ),
        "K",
        {"type": "parabola_shape", "f": a * x**2, "answer": answer},
        wrong_kinds=kinds,
    )


@variant("1.1", G10, example=2)
def parabola_through_point(rng: random.Random) -> Problem:
    p = rng.choice([-4, -3, -2, 2, 3, 4])
    halves = [HALF, -HALF, sp.Rational(3, 2), -sp.Rational(3, 2)] if p % 2 == 0 else []
    a = rng.choice([-4, -3, -2, -1, 1, 2, 3, 4, *halves])
    q = a * p * p
    wrong, kinds = tagged_wrongs(
        a, ("square", a * p), ("square", q * p * p), ("sign", -a), ("formula", q - p * p)
    )
    return Problem(
        "1.1",
        f"يمرّ التمثيل البياني للدالة $f(x)=ax^2$ بالنقطة $({p},{tex(q)})$. أوجد قيمة $a$.",
        m(a),
        wrong,
        (
            f"نعوّض إحداثيي النقطة في قاعدة الدالة: ${tex(q)}=a({p})^2$",
            f"${tex(q)}={p * p}a$",
            f"$a={frac(q, p * p)}={tex(a)}$",
        ),
        "K",
        {"type": "value", "f": a * x**2, "at": p, "value": q},
        wrong_kinds=kinds,
    )


@variant("1.1", G10, example=1)
def parabola_monotone_interval(rng: random.Random) -> Problem:
    a = scale(rng)
    increasing = rng.random() < 0.5
    right = bool(a > 0) == increasing
    word = "متزايدة" if increasing else "متناقصة"
    answer, other = ("$x>0$", "$x<0$") if right else ("$x<0$", "$x>0$")
    wrong = (other, "جميع الأعداد الحقيقية", f"$x>{tex(a)}$")
    kinds = ("direction", "concept", "coefficient")
    return Problem(
        "1.1",
        f"حدّد الفترة التي تكون فيها الدالة $f(x)={ax2(a)}$ {word}.",
        answer,
        wrong,
        (
            f"$a={tex(a)}$ {sign_word(a)}، فالقطع المكافئ يفتح إلى {opening(a)}، ورأسه $(0,0)$.",
            f"الدالة {word} على {'يمين' if right else 'يسار'} محور التماثل $x=0$، أي عندما {answer}.",
        ),
        "K",
        {"type": "parabola_monotone", "f": a * x**2, "increasing": increasing, "answer": answer},
        wrong_kinds=kinds,
    )


@variant("1.1", G10, example=3)
def parabola_rule_from_table(rng: random.Random) -> Problem:
    a = rng.choice([-4, -3, -2, -1, 1, 2, 3, 4, HALF, -HALF])
    xs = (-4, -2, 0, 2, 4) if abs(a) == HALF else (-2, -1, 0, 1, 2)
    at = rng.choice([6, -6, 8, -8] if abs(a) == HALF else [3, -3, 4, -4, 5])
    values = [a * v * v for v in xs]
    value = a * at * at
    p = xs[-1]
    header = " & ".join(str(v) for v in xs)
    row = " & ".join(tex(v) for v in values)
    table = rf"\begin{{array}}{{c|ccccc}} x & {header} \\ \hline f(x) & {row} \end{{array}}"

    def text(da: Any, dv: Any) -> str:
        return f"$a={tex(da)}$، و$f({at})={tex(dv)}$"

    answer = text(a, value)
    wrong, kinds = tagged_wrongs(
        answer,
        ("square", text(a, a * at)),
        ("sign", text(-a, -value)),
        ("coefficient", text(a * p, a * p * at * at)),
        ("formula", text(a, 2 * a * at)),
    )
    return Problem(
        "1.1",
        f"يبيّن الجدول قيمًا للدالة $f(x)=ax^2$: ${table}$ أوجد قيمة $a$، ثم أوجد $f({at})$.",
        answer,
        wrong,
        (
            f"من الجدول $f({p})={tex(a * p * p)}$، فنعوّض في القاعدة: ${tex(a * p * p)}=a({p})^2$",
            f"$a={frac(a * p * p, p * p)}={tex(a)}$",
            f"$f({at})={lead(a)}({at})^2={tex(value)}$",
        ),
        "K",
        {"type": "table_rule", "xs": xs, "values": tuple(values), "at": at, "answer": answer},
        wrong_kinds=kinds,
    )


@variant("1.1", G10, example=4)
def square_area_cost(rng: random.Random) -> Problem:
    work, place = rng.choice([("تبليط", "أرضية"), ("تعشيب", "حديقة"), ("رصف", "ساحة")])
    rate = 5 * rng.randint(3, 12)
    side = rng.randint(3, 10)
    cost = rate * side * side
    unit = "ريال"
    answer = with_unit(cost, unit)
    wrong, kinds = tagged_wrongs(
        answer,
        ("square", with_unit(rate * side, unit)),
        ("formula", with_unit(2 * rate * side, unit)),
        ("formula", with_unit(rate + side * side, unit)),
    )
    return Problem(
        "1.1",
        f"تُعطى تكلفة {work} {place} مربعة الشكل طول ضلعها $x$ من الأمتار بالريال بالدالة "
        f"$f(x)={rate}x^2$. أوجد تكلفة {work} {place} طول ضلعها ${side}$ أمتار.",
        answer,
        wrong,
        (
            f"نعوّض $x={side}$: $f({side})={rate}({side})^2$",
            f"$f({side})={rate}\\times{side * side}={cost}$",
        ),
        "K",
        {"type": "value", "f": rate * x**2, "at": side, "value": cost},
        wrong_kinds=kinds,
    )


@variant("1.1", G10, example=5)
def parabola_average_rate(rng: random.Random) -> Problem:
    a = rng.choice([-4, -3, -2, -1, 1, 2, 3, 4])
    p = rng.randint(-4, 3)
    q = rng.choice([n for n in range(p + 1, p + 5) if n != -p])
    low, high = a * p * p, a * q * q
    value = a * (p + q)
    wrong, kinds = tagged_wrongs(
        value,
        ("formula", high - low),
        ("formula", a * (q - p)),
        ("sign", sp.Rational(high + low, q - p)),
    )
    return Problem(
        "1.1",
        f"أوجد متوسط معدل التغيّر للدالة $f(x)={ax2(a)}$ في الفترة ${p} \\le x \\le {q}$.",
        m(value),
        wrong,
        (
            f"$f({p})={low}$ و$f({q})={high}$",
            f"${frac(f'f({q})-f({p})', minus(q, p))}={frac(high - low, q - p)}={value}$",
        ),
        "A",
        {"type": "average", "f": a * x**2, "a": p, "b": q, "value": value},
        wrong_kinds=kinds,
    )


# الدرس 1.2: الدوال التربيعية في صيغة الرأس f(x)=a(x-h)²+k
def vertex_text(h: int, k: int) -> str:
    return f"الرأس $({h},{k})$، ومحور التماثل $x={h}$"


def translation_text(h: int, k: int) -> str:
    return (
        f"إزاحة {units(abs(h))} إلى {RIGHT if h > 0 else LEFT}، و{units(abs(k))} إلى {UP if k > 0 else DOWN}"
    )


# معامل الدالة الرئيسة في أسئلة الإزاحة: الإزاحة لا تغيّر الاتساع ولا اتجاه الفتحة.
PARENT_SCALES = (1, -1, 2, -2, 3, HALF)


def shift_text(steps: int, direction: str, vertex: tuple[int, int]) -> str:
    return f"إزاحة {units(steps)} إلى {direction}، والرأس $({vertex[0]},{vertex[1]})$"


@variant("1.2", G10, example=1)
def vertical_shift_of_parent(rng: random.Random) -> Problem:
    a, k = rng.choice(PARENT_SCALES), nz(rng, -8, 8)
    up, side = (UP, RIGHT) if k > 0 else (DOWN, LEFT)
    flipped = DOWN if k > 0 else UP
    answer = shift_text(abs(k), up, (0, k))
    wrong = (
        shift_text(abs(k), flipped, (0, -k)),
        shift_text(abs(k), side, (k, 0)),
        shift_text(abs(k), up, (k, 0)),
    )
    kinds = ("direction", "concept", "swap")
    return Problem(
        "1.2",
        f"صف كيف ينتج التمثيل البياني للدالة $g(x)={ax2(a)}{signed(k)}$ من التمثيل البياني للدالة "
        f"$f(x)={ax2(a)}$، وحدّد رأسه.",
        answer,
        wrong,
        (
            f"$g(x)=f(x){signed(k)}$: نضيف ${k}$ إلى كل قيمة من قيم $f$، فكل نقطة تنتقل رأسيًا.",
            f"$k={k}$ {sign_word(k)}، فالإزاحة {units(abs(k))} إلى {up}.",
            f"رأس $f$ هو $(0,0)$، فرأس $g$ هو $(0,{k})$.",
        ),
        "K",
        {"type": "vertical_shift", "f": a * x**2, "g": a * x**2 + k, "answer": answer},
        wrong_kinds=kinds,
    )


@variant("1.2", G10, example=2)
def horizontal_shift_of_parent(rng: random.Random) -> Problem:
    a, h = rng.choice(PARENT_SCALES), nz(rng, -6, 6)
    side, flipped = (RIGHT, LEFT) if h > 0 else (LEFT, RIGHT)
    up = UP if h > 0 else DOWN
    answer = shift_text(abs(h), side, (h, 0))
    wrong = (
        shift_text(abs(h), flipped, (-h, 0)),
        shift_text(abs(h), up, (0, h)),
        shift_text(abs(h), flipped, (h, 0)),
    )
    kinds = ("direction", "concept", "partial")
    return Problem(
        "1.2",
        f"صف كيف ينتج التمثيل البياني للدالة $g(x)={lead(a)}{shifted(h)}^2$ من التمثيل البياني للدالة "
        f"$f(x)={ax2(a)}$، وحدّد رأسه.",
        answer,
        wrong,
        (
            f"$g(x)=f(x-h)$ حيث $h={h}$: الدالة $g$ تأخذ عند $x={h}$ القيمة التي تأخذها $f$ عند $x=0$.",
            f"$h={h}$ {sign_word(h)}، فالإزاحة {units(abs(h))} إلى {side}.",
            f"رأس $f$ هو $(0,0)$، فرأس $g$ هو $({h},0)$.",
        ),
        "K",
        {"type": "horizontal_shift", "f": a * x**2, "g": a * (x - h) ** 2, "answer": answer},
        wrong_kinds=kinds,
    )


@variant("1.2", G10, example=4)
def mirror_of_y_intercept(rng: random.Random) -> Problem:
    a, h, k = rng.choice(INTEGER_SCALES), nz(rng, -4, 4), rng.randint(-9, 9)
    c = a * h * h + k

    def text(px: int, value: int) -> str:
        return f"المقطع $y$ هو $(0,{value})$، ونظيره حول محور التماثل $({px},{value})$"

    answer = text(2 * h, c)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", text(-2 * h, c)),
        ("coefficient", text(2 * h, k)),
        ("formula", text(h, c)),
        ("sign", text(2 * h, -a * h * h + k)),
    )
    return Problem(
        "1.2",
        f"للدالة $f(x)={vertex_form(a, h, k)}$، أوجد المقطع $y$ لتمثيلها البياني، والنقطة المناظرة له "
        "حول محور التماثل.",
        answer,
        wrong,
        (
            f"الرأس $({h},{k})$، ومحور التماثل $x={h}$.",
            f"المقطع $y$: $f(0)={lead(a)}({minus(0, h)})^2{signed(k)}={c}$، أي النقطة $(0,{c})$.",
            f"النقطة $(0,{c})$ تبعد ${abs(h)}$ عن المحور، فنظيرها على البعد نفسه في الجهة الأخرى: "
            f"$x={h}+({h})={2 * h}$، أي $({2 * h},{c})$.",
        ),
        "A",
        {"type": "mirror_point", "f": a * (x - h) ** 2 + k, "point": (2 * h, c), "answer": answer},
        wrong_kinds=kinds,
    )


@variant("1.2", G10, example=3)
def vertex_and_axis_from_vertex_form(rng: random.Random) -> Problem:
    a = rng.choice([*INTEGER_SCALES, HALF, -HALF])
    h = nz(rng, -6, 6)
    k = rng.choice([n for n in range(-8, 9) if n not in (0, h, -h)])
    wrong = (vertex_text(-h, k), vertex_text(h, -k), vertex_text(k, h))
    kinds = ("sign", "sign", "swap")
    return Problem(
        "1.2",
        f"حدّد إحداثيي رأس القطع المكافئ ومعادلة محور التماثل للدالة $f(x)={vertex_form(a, h, k)}$.",
        vertex_text(h, k),
        wrong,
        (
            "الدالة مكتوبة في صيغة الرأس $f(x)=a(x-h)^2+k$، ورأس القطع المكافئ $(h,k)$.",
            f"بالمقارنة: $h={h}$ و$k={k}$، فالرأس $({h},{k})$.",
            f"محور التماثل هو المستقيم الرأسي المارّ بالرأس: $x={h}$.",
        ),
        "K",
        {"type": "vertex", "f": a * (x - h) ** 2 + k, "vertex": (h, k)},
        wrong_kinds=kinds,
    )


@variant("1.2", G10, example=3)
def translation_of_parent(rng: random.Random) -> Problem:
    h, k = nz(rng, -6, 6), nz(rng, -6, 6)
    answer = translation_text(h, k)
    wrong = (translation_text(-h, k), translation_text(h, -k), translation_text(-h, -k))
    kinds = ("sign", "sign", "sign")
    return Problem(
        "1.2",
        f"صف كيف ينتج التمثيل البياني للدالة $g(x)={vertex_form(1, h, k)}$ من التمثيل البياني "
        "للدالة $f(x)=x^2$.",
        answer,
        wrong,
        (
            f"$h={h}$: إزاحة أفقية {units(abs(h))} إلى {RIGHT if h > 0 else LEFT}.",
            f"$k={k}$: إزاحة رأسية {units(abs(k))} إلى {UP if k > 0 else DOWN}.",
        ),
        "K",
        {"type": "translation", "g": (x - h) ** 2 + k, "text": answer},
        wrong_kinds=kinds,
    )


@variant("1.2", G10, example=3)
def rule_from_translation(rng: random.Random) -> Problem:
    h, k = nz(rng, -6, 6), nz(rng, -6, 6)

    def rule(dh: int, dk: int) -> str:
        return f"$g(x)={vertex_form(1, dh, dk)}$"

    stem = (
        f"أُزيح التمثيل البياني للدالة $f(x)=x^2$ {units(abs(h))} إلى {RIGHT if h > 0 else LEFT}، "
        f"و{units(abs(k))} إلى {UP if k > 0 else DOWN}. اكتب قاعدة الدالة الناتجة $g$ في صيغة الرأس."
    )
    wrong = (rule(-h, k), rule(h, -k), rule(-h, -k))
    kinds = ("sign", "sign", "sign")
    return Problem(
        "1.2",
        stem,
        rule(h, k),
        wrong,
        (
            f"الإزاحة الأفقية تعطي $h={h}$، والإزاحة الرأسية تعطي $k={k}$.",
            f"نعوّض في $g(x)=(x-h)^2+k$: $g(x)={vertex_form(1, h, k)}$",
        ),
        "K",
        {"type": "translation", "g": (x - h) ** 2 + k, "text": stem},
        wrong_kinds=kinds,
    )


@variant("1.2", G10, example=5)
def vertex_form_from_vertex_and_point(rng: random.Random) -> Problem:
    a = rng.choice([*INTEGER_SCALES, HALF, -HALF])
    h = nz(rng, -5, 5)
    k = rng.choice([n for n in range(-6, 7) if n not in (0, h)])
    d = rng.choice([2, -2] if abs(a) == HALF else [1, -1, 2, -2, 3, -3])
    p, q = h + d, int(a * d * d + k)

    def rule(da: Any, dh: int, dk: int) -> str:
        return f"$f(x)={vertex_form(da, dh, dk)}$"

    answer = rule(a, h, k)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", rule(a, -h, k)),
        ("sign", rule(-a, h, k)),
        ("swap", rule(a, k, h)),
        ("sign", rule(a, h, -k)),
        ("sign", rule(-a, -h, k)),
    )
    return Problem(
        "1.2",
        f"رأس قطع مكافئ هو النقطة $({h},{k})$، ويمرّ القطع بالنقطة $({p},{q})$. "
        "اكتب قاعدة الدالة التربيعية التي تمثّله في صيغة الرأس.",
        answer,
        wrong,
        (
            f"نعوّض الرأس في صيغة الرأس: $f(x)=a{shifted(h)}^2{signed(k)}$",
            f"نعوّض النقطة $({p},{q})$: ${q}=a({minus(p, h)})^2{signed(k)}$",
            f"إذن $a={q - k}$" if d * d == 1 else f"${q - k}={d * d}a$، إذن $a={tex(a)}$",
        ),
        "A",
        {"type": "vertex_point", "f": a * (x - h) ** 2 + k, "vertex": (h, k), "point": (p, q)},
        wrong_kinds=kinds,
    )


def ball_wrongs(answer: str, peak: int, at: int, start: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """أخطاء شائعة في مسألة أقصى ارتفاع: ارتفاع البداية، وزمن العودة إليه، وتبديل الإحداثيين."""
    unit = "مترًا"
    return tagged_wrongs(
        answer,
        ("partial", f"{with_unit(peak, unit)} عند $x={2 * at}$"),
        ("formula", f"{with_unit(10 * at, unit)} عند $x={at}$"),
        ("formula", f"{with_unit(peak + start, unit)} عند $x={at}$"),
    )


@variant("1.2", G10, example=5)
def ball_height_vertex_form(rng: random.Random) -> Problem:
    at, start = rng.randint(2, 4), rng.randint(1, 9)
    peak = 5 * at * at + start
    answer = f"{with_unit(peak, 'مترًا')} عند $x={at}$"
    wrong, kinds = ball_wrongs(answer, peak, at, start)
    return Problem(
        "1.2",
        "قُذفت كرة إلى الأعلى، ويُعطى ارتفاعها بالأمتار بعد $x$ من الثواني بالدالة "
        f"$f(x)={vertex_form(-5, at, peak)}$. أوجد أقصى ارتفاع تبلغه الكرة والزمن الذي تبلغه عنده.",
        answer,
        wrong,
        (
            "الدالة في صيغة الرأس و$a=-5$ سالب، فللدالة قيمة عظمى عند رأس القطع المكافئ.",
            f"الرأس $({at},{peak})$.",
            f"أقصى ارتفاع ${peak}$ مترًا، وتبلغه الكرة عند $x={at}$.",
        ),
        "A",
        {
            "type": "optimum",
            "f": -5 * (x - at) ** 2 + peak,
            "low": 0,
            "high": 2 * at,
            "arg": at,
            "value": peak,
            "max": True,
        },
        wrong_kinds=kinds,
    )


# الدرس 1.3: الدوال التربيعية في الصيغة القياسية f(x)=ax²+bx+c
@variant("1.3", G10, example=2)
def axis_and_vertex_from_standard_form(rng: random.Random) -> Problem:
    a, h, k = rng.choice(INTEGER_SCALES), nz(rng, -4, 4), rng.randint(-9, 9)
    f, b, c = standard_from_vertex(a, h, k)

    def text(px: int) -> str:
        return f"محور التماثل $x={px}$، والرأس $({px},{a * px * px + b * px + c})$"

    answer = text(h)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", text(-h)),
        ("formula", text(2 * h)),
        ("coefficient", f"محور التماثل $x={h}$، والرأس $({h},{c})$"),
        ("sign", text(-2 * h)),
    )
    return Problem(
        "1.3",
        f"أوجد معادلة محور التماثل وإحداثيي رأس القطع المكافئ للدالة $f(x)={tex(f)}$.",
        answer,
        wrong,
        (
            f"$a={a}$ و$b={b}$، فمحور التماثل {axis_step(a, b, h)}",
            f"الإحداثي $y$ للرأس: {value_step(a, b, c, h, k)}",
            f"الرأس $({h},{k})$.",
        ),
        "K",
        {"type": "vertex", "f": f, "vertex": (h, k)},
        wrong_kinds=kinds,
    )


@variant("1.3", G10, example=1)
def intercept_and_opening_from_standard_form(rng: random.Random) -> Problem:
    a, b = nz(rng, -4, 4), nz(rng, -9, 9)
    c = rng.choice([n for n in range(-9, 10) if n not in (0, a, b)])
    f = a * x**2 + b * x + c
    up = a > 0

    def text(value: int, opens_up: bool) -> str:
        return f"المقطع $y$ هو ${value}$، ويفتح القطع المكافئ إلى {UP if opens_up else DOWN}"

    answer = text(c, up)
    wrong, kinds = tagged_wrongs(
        answer,
        ("direction", text(c, not up)),
        ("coefficient", text(b, up)),
        ("coefficient", text(a, not up)),
        ("coefficient", text(b, not up)),
    )
    return Problem(
        "1.3",
        f"حدّد المقطع $y$ للتمثيل البياني للدالة $f(x)={tex(f)}$ واتجاه فتحة القطع المكافئ.",
        answer,
        wrong,
        (
            f"المقطع $y$ هو قيمة الدالة عند $x=0$: $f(0)={c}$.",
            f"$a={a}$ {sign_word(a)}، فالقطع المكافئ يفتح إلى {opening(a)}.",
        ),
        "K",
        {"type": "standard_features", "f": f, "answer": answer},
        wrong_kinds=kinds,
    )


def extreme_text(is_max: bool, value: int) -> str:
    return f"قيمة {'عظمى' if is_max else 'صغرى'} تساوي ${value}$"


@variant("1.3", G10, example=3)
def extreme_value_from_standard_form(rng: random.Random) -> Problem:
    a, h, k = rng.choice(INTEGER_SCALES), nz(rng, -4, 4), rng.randint(-9, 9)
    f, b, c = standard_from_vertex(a, h, k)
    is_max = a < 0
    answer = extreme_text(is_max, k)
    wrong, kinds = tagged_wrongs(
        answer,
        ("concept", extreme_text(not is_max, k)),
        ("coefficient", extreme_text(is_max, c)),
        ("coefficient", extreme_text(not is_max, c)),
        ("swap", extreme_text(is_max, h)),
    )
    return Problem(
        "1.3",
        f"هل للدالة $f(x)={tex(f)}$ قيمة عظمى أم قيمة صغرى؟ أوجد هذه القيمة.",
        answer,
        wrong,
        (
            f"$a={a}$ {sign_word(a)}، فالقطع المكافئ يفتح إلى {opening(a)}، وللدالة قيمة "
            f"{'عظمى' if is_max else 'صغرى'} عند الرأس.",
            f"محور التماثل {axis_step(a, b, h)}",
            value_step(a, b, c, h, k),
        ),
        "A",
        {"type": "parabola_extreme", "f": f, "at": h, "value": k, "answer": answer},
        wrong_kinds=kinds,
    )


@variant("1.3", G10, example=3)
def compare_maximum_values(rng: random.Random) -> Problem:
    """مقارنة دالتين ممثلتين بصيغتين مختلفتين: f جبريًا في الصيغة القياسية، وg بوصف رأسها."""
    a, h, top_f = rng.choice([-1, -2, -3]), nz(rng, -3, 3), rng.randint(3, 12)
    top_g = rng.choice([n for n in range(1, 16) if n != top_f])
    h_g = nz(rng, -5, 5)
    f, b, c = standard_from_vertex(a, h, top_f)
    larger, smaller = ("f", "g") if top_f > top_g else ("g", "f")
    gap = abs(top_f - top_g)

    def text(name: str, value: int) -> str:
        return f"الدالة ${name}$، والفرق ${value}$"

    answer = text(larger, gap)
    wrong, kinds = tagged_wrongs(
        answer,
        ("partial", text(smaller, gap)),
        ("formula", text(larger, top_f + top_g)),
        ("formula", text(smaller, top_f + top_g)),
        ("nearby", text(larger, gap + 1)),
    )
    return Problem(
        "1.3",
        f"الدالة $f(x)={tex(f)}$، والدالة $g$ دالة تربيعية يفتح تمثيلها البياني إلى الأسفل ورأسه "
        f"$({h_g},{top_g})$. أيّ الدالتين قيمتها العظمى أكبر؟ وما الفرق بين القيمتين العظميين؟",
        answer,
        wrong,
        (
            f"$a={a}$ سالب، فللدالة $f$ قيمة عظمى عند الرأس، ومحور التماثل {axis_step(a, b, h)}",
            f"القيمة العظمى للدالة $f$: {value_step(a, b, c, h, top_f)}",
            f"القيمة العظمى للدالة $g$ هي الإحداثي $y$ لرأسها: ${top_g}$.",
            f"الفرق ${max(top_f, top_g)}-{min(top_f, top_g)}={gap}$، والقيمة العظمى للدالة ${larger}$ أكبر.",
        ),
        "A",
        {
            "type": "compare_maxima",
            "f": f,
            "low": h - 6,
            "high": h + 6,
            "other": top_g,
            "answer": answer,
        },
        wrong_kinds=kinds,
    )


@variant("1.3", G10, example=4)
def ball_height_standard_form(rng: random.Random) -> Problem:
    at, start = rng.randint(2, 4), rng.randint(1, 9)
    peak = 5 * at * at + start
    f, b, c = standard_from_vertex(-5, at, peak)
    answer = f"{with_unit(peak, 'مترًا')} عند $x={at}$"
    wrong, kinds = ball_wrongs(answer, peak, at, start)
    return Problem(
        "1.3",
        "رُميت كرة إلى الأعلى، ويُعطى ارتفاعها بالأمتار بعد $x$ من الثواني بالدالة "
        f"$f(x)={tex(f)}$. أوجد أقصى ارتفاع تبلغه الكرة والزمن الذي تبلغه عنده.",
        answer,
        wrong,
        (
            f"$a=-5$ سالب، فللدالة قيمة عظمى عند الرأس، ومحور التماثل {axis_step(-5, b, at)}",
            value_step(-5, b, c, at, peak),
            f"أقصى ارتفاع ${peak}$ مترًا، وتبلغه الكرة عند $x={at}$.",
        ),
        "A",
        {"type": "optimum", "f": f, "low": 0, "high": 2 * at, "arg": at, "value": peak, "max": True},
        wrong_kinds=kinds,
    )


# «اكتشف الخطأ» في الوحدة 1: الزلّة → (رقم الخطوة التي تقع فيها، نوع الخطأ من ERROR_KINDS).
AVERAGE_RATE_SLIPS = {
    "unsquared": (1, "square"),  # ضرب المعامل في x بلا تربيع
    "doubled": (2, "square"),  # ضاعف x بدل تربيعه
    "interval_sign": (3, "sign"),  # طرح عددًا سالبًا دون تغيير إشارته
    "reversed": (4, "swap"),  # بدّل ترتيب قيمتي الدالة في البسط
    "undivided": (4, "formula"),  # لم يقسم على طول الفترة
}
VERTEX_POINT_SLIPS = {
    "bracket_sign": (1, "sign"),  # عكس إشارة h داخل القوس
    "unsquared": (2, "square"),  # لم يربّع ما داخل القوس
    "moved_sign": (3, "sign"),  # نقل الحد الثابت دون تغيير إشارته
    "inverted": (4, "swap"),  # قسم المعامل على الطرف الآخر
    "multiplied": (4, "formula"),  # ضرب بدل القسمة
}
STANDARD_VERTEX_SLIPS = {
    "axis_sign": (1, "sign"),  # أسقط الإشارة السالبة من قانون محور التماثل
    "axis_no_two": (1, "formula"),  # قسم على a بدل 2a
    "unsquared": (2, "square"),  # عوّض في الحد التربيعي بلا تربيع
    "negative_square": (2, "sign"),  # جعل مربع العدد السالب سالبًا
    "swapped": (3, "swap"),  # بدّل إحداثيي الرأس
}


def average_rate_item(a: int, p: int, q: int, slip: str) -> ErrorSpotting | None:
    step, kind = AVERAGE_RATE_SLIPS[slip]
    low, high, width = ref(1), ref(2), ref(3)
    rules: tuple[Rule, ...] = ((a * p * p,), (a * q * q,), (q - p,), ((high - low) / width,))
    wrong: Rule = {
        "unsquared": (a * p,),
        "doubled": (2 * a * q,),
        "interval_sign": (q + p,),
        "reversed": ((low - high) / width,),
        "undivided": (high - low,),
    }[slip]
    if slip == "interval_sign" and p >= 0:  # الزلّة في طرح عدد سالب
        return None

    def texts(rows: list[Row], slipped: bool) -> tuple[str, ...]:
        (start,), (end,), (length,), (rate,) = rows
        top = minus(start, end) if slipped and slip == "reversed" else minus(end, start)
        change = top if slipped and slip == "undivided" else frac(top, length)
        return (
            f"نحسب قيمة الدالة عند بداية الفترة: $f({p})={lead(a)}({p})^2={start}$",
            f"نحسب قيمة الدالة عند نهاية الفترة: $f({q})={lead(a)}({q})^2={end}$",
            f"نحسب طول الفترة: ${minus(q, p)}={length}$",
            f"متوسط معدل التغيّر: ${change}={exact(rate)}$",
        )

    return spotted_values(
        "1.1",
        f"أوجد طالب متوسط معدل التغيّر للدالة $f(x)={ax2(a)}$ في الفترة ${p} \\le x \\le {q}$ {SPOT_TASK}",
        rules,
        (step, kind, wrong),
        texts,
        m(a * (p + q)),
        {"quantity": "average_rate", "f": a * x**2, "a": p, "b": q},
    )


@variant("1.1", G10, example=5, registry=ERROR_SPOTTING)
def spot_error_in_average_rate(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(AVERAGE_RATE_SLIPS))
    while True:
        a, p = rng.choice([-4, -3, -2, -1, 1, 2, 3, 4]), rng.randint(-4, 3)
        q = rng.choice([n for n in range(p + 1, p + 5) if n != -p])
        item = average_rate_item(a, p, q, slip)
        if item is not None:
            return item


def vertex_point_item(a: int, h: int, k: int, d: int, slip: str) -> ErrorSpotting | None:
    step, kind = VERTEX_POINT_SLIPS[slip]
    p, q = h + d, a * d * d + k
    gap, square, moved, found = ref(1), ref(2), ref(3), ref(4)
    rules: tuple[Rule, ...] = ((p - h,), (gap**2,), (q - k,), (moved / square,), (found,))
    wrong: Rule = {
        "bracket_sign": (p + h,),
        "unsquared": (gap,),
        "moved_sign": (q + k,),
        "inverted": (square / moved,),
        "multiplied": (moved * square,),
    }[slip]

    def texts(rows: list[Row], slipped: bool) -> tuple[str, ...]:
        _, (factor,), (left,), (value,), _ = rows
        bracket = f"{p}{h:+d}" if slipped and slip == "bracket_sign" else minus(p, h)
        difference = f"{q}{k:+d}" if slipped and slip == "moved_sign" else minus(q, k)
        if slipped and slip == "multiplied":
            solving = f"{left}\\times{factor if factor >= 0 else f'({factor})'}={exact(value)}"
        elif slipped and slip == "inverted":
            solving = quotient(factor, left)
        else:
            solving = quotient(left, factor)
        return (
            f"نعوّض الرأس والنقطة في صيغة الرأس: ${q}=a({bracket})^2{signed(k)}$",
            f"نبسّط ما داخل القوس ونربّعه: ${q}={lead(factor)}a{signed(k)}$",
            f"ننقل الحد الثابت إلى الطرف الأيسر: ${difference}={lead(factor)}a$، أي ${left}={lead(factor)}a$",
            f"نوجد قيمة $a$: $a={solving}$",
            f"إذن $f(x)={vertex_form(value, h, k)}$",
        )

    item = spotted_values(
        "1.2",
        f"رأس قطع مكافئ هو النقطة $({h},{k})$، ويمرّ القطع بالنقطة $({p},{q})$. كتب طالب قاعدة الدالة "
        f"التربيعية التي تمثّله في صيغة الرأس {SPOT_TASK}",
        rules,
        (step, kind, wrong),
        texts,
        f"$f(x)={vertex_form(a, h, k)}$",
        {"quantity": "leading_coefficient", "vertex": (h, k), "point": (p, q)},
    )
    # معامل صفري في الحل المعروض لا يترك دالة تربيعية
    return None if item is None or item.check["steps"][-1][0] == 0 else item


@variant("1.2", G10, example=5, registry=ERROR_SPOTTING)
def spot_error_in_vertex_form_from_point(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(VERTEX_POINT_SLIPS))
    while True:
        a, h, k = rng.choice(INTEGER_SCALES), nz(rng, -5, 5), nz(rng, -6, 6)
        item = vertex_point_item(a, h, k, rng.choice([-3, -2, -1, 1, 2, 3]), slip)
        if item is not None:
            return item


def standard_vertex_item(a: int, h: int, k: int, slip: str) -> ErrorSpotting | None:
    step, kind = STANDARD_VERTEX_SLIPS[slip]
    f, b, c = standard_from_vertex(a, h, k)
    at = ref(1)

    def terms(first: Any) -> Rule:
        """حدّا التعويض ثم مجموعهما مع الحد الثابت."""
        return (first, b * at, first + b * at + c)

    rules: tuple[Rule, ...] = ((sp.Rational(-b, 2 * a),), terms(a * at**2), (at, ref(2, 2)))
    wrong: Rule = {
        "axis_sign": (sp.Rational(b, 2 * a),),
        "axis_no_two": (sp.Rational(-b, a),),
        "unsquared": terms(a * at),
        "negative_square": terms(-a * at**2),
        "swapped": (ref(2, 2), at),
    }[slip]
    if slip == "negative_square" and h > 0:  # الزلّة في تربيع عدد سالب
        return None

    def texts(rows: list[Row], slipped: bool) -> tuple[str, ...]:
        (axis,), (first, second, total), (px, py) = (tuple(int(value) for value in row) for row in rows)
        formula = f"-\\dfrac{{b}}{{2a}}=-\\dfrac{{{b}}}{{2({a})}}"
        if slipped and slip == "axis_sign":
            formula = f"\\dfrac{{b}}{{2a}}=\\dfrac{{{b}}}{{2({a})}}"
        elif slipped and slip == "axis_no_two":
            formula = f"-\\dfrac{{b}}{{a}}=-\\dfrac{{{b}}}{{{a}}}"
        return (
            f"$a={a}$ و$b={b}$، فمحور التماثل $x={formula}={axis}$",
            f"نعوّض في قاعدة الدالة: $f({axis})={lead(a)}({axis})^2{b:+d}({axis}){signed(c)}"
            f"={first}{second:+d}{signed(c)}={total}$",
            f"إذن رأس القطع المكافئ $({px},{py})$",
        )

    return spotted_values(
        "1.3",
        f"أوجد طالب محور التماثل ورأس القطع المكافئ للدالة $f(x)={tex(f)}$ {SPOT_TASK}",
        rules,
        (step, kind, wrong),
        texts,
        f"محور التماثل $x={h}$، والرأس $({h},{k})$",
        {"quantity": "vertex", "f": f},
    )


@variant("1.3", G10, example=2, registry=ERROR_SPOTTING)
def spot_error_in_vertex_from_standard_form(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(STANDARD_VERTEX_SLIPS))
    while True:
        item = standard_vertex_item(rng.choice(INTEGER_SCALES), nz(rng, -4, 4), rng.randint(-9, 9), slip)
        if item is not None:
            return item


# الوحدة 2 (أ): حل المعادلات التربيعية
SQUARE_FREE = (2, 3, 5, 6, 7, 10, 11, 13)
COUNTS = {0: "لا يوجد حل حقيقي", 1: "حل حقيقي واحد", 2: "حلّان حقيقيان مختلفان"}
COUNT_PHRASES = {
    0: "ليس للمعادلة حل حقيقي",
    1: "للمعادلة حل حقيقي واحد",
    2: "للمعادلة حلّان حقيقيان مختلفان",
}


def solutions(*roots: Any) -> str:
    """حلول المعادلة مرتبة تصاعديًا: «x=r₁ أو x=r₂»."""
    return " أو ".join(f"$x={tex(r)}$" for r in sorted(set(roots)))


def solution_wrongs(answer: str, r1: Any, r2: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """أخطاء الإشارة أولًا ثم قيم قريبة؛ الثلاثة الأخيرة تختلف دائمًا عن الجواب وعن بعضها."""
    return tagged_wrongs(
        answer,
        ("sign", solutions(-r1, -r2)),
        ("sign", solutions(-r1, r2)),
        ("sign", solutions(r1, -r2)),
        ("nearby", solutions(r1 + 1, r2 + 1)),
        ("nearby", solutions(r1 - 1, r2 - 1)),
        ("nearby", solutions(r1, r2 + 1)),
    )


def linear(r: int) -> str:
    """العامل x-r بلا قوسين."""
    return f"x{-r:+d}" if r else "x"


def product(r1: int, r2: int) -> str:
    """(x-r₁)(x-r₂)، والعامل x أولًا إن كان أحد الجذرين صفرًا."""
    first, second = (r2, r1) if r2 == 0 else (r1, r2)
    return f"{shifted(first)}{shifted(second)}"


def two_roots(rng: random.Random, low: int, high: int, zero: bool = True) -> tuple[int, int]:
    first, second = sorted(rng.sample([n for n in range(low, high + 1) if zero or n], 2))
    return first, second


def plus(left: int, right: int) -> str:
    return f"{left}+{right}" if right >= 0 else f"{left}+({right})"


def root(coefficient: int, radicand: Any) -> str:
    """c√m نصًّا، ويُحذف المعامل واحد."""
    return f"{'' if coefficient == 1 else coefficient}\\sqrt{{{radicand}}}"


def square_free(n: int) -> bool:
    return all(n % (d * d) for d in range(2, math.isqrt(n) + 1))


def tenth(value: float) -> str:
    return f"{value:.1f}"


def projectile(rng: random.Random) -> tuple[sp.Expr, int, int, int, float, float]:
    """(دالة الارتفاع -5x²+vx+s، v، s، المميز، الجذر السالب، الجذر الموجب) بجذرين غير نسبيين."""
    while True:
        v, s = 5 * rng.randint(1, 6), rng.randint(1, 9)
        disc = v * v + 20 * s
        low, high = (v - math.sqrt(disc)) / 10, (v + math.sqrt(disc)) / 10
        if math.isqrt(disc) ** 2 != disc and low < -0.05:
            return -5 * x**2 + v * x + s, v, s, disc, low, high


def seconds(value: float | int) -> str:
    return f"${value if isinstance(value, int) else tenth(value)}$ ثانية تقريبًا"


# الدرس 2.1: حل المعادلات التربيعية باستعمال التمثيلات البيانية والجداول
@variant("2.1", G10, example=1)
def solutions_from_x_intercepts(rng: random.Random) -> Problem:
    r1, r2 = two_roots(rng, -7, 7)
    f = sp.expand(rng.choice([-2, -1, 1, 2]) * (x - r1) * (x - r2))
    answer = solutions(r1, r2)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", solutions(-r1, -r2)),
        ("concept", f"$x={f.subs(x, 0)}$"),
        ("nearby", solutions(r1 + 1, r2 + 1)),
        ("partial", solutions(r1)),
        ("partial", solutions(r2)),
    )
    return Problem(
        "2.1",
        f"يقطع التمثيل البياني للدالة $f(x)={tex(f)}$ المحور $x$ عند النقطتين $({r1},0)$ و$({r2},0)$. "
        f"ما حلول المعادلة ${tex(f)}=0$؟",
        answer,
        wrong,
        (
            "حلول المعادلة $f(x)=0$ هي أصفار الدالة $f$، أي الإحداثيات $x$ لنقاط تقاطع تمثيلها البياني "
            "مع المحور $x$.",
            f"المقطعان $x$ هما ${r1}$ و${r2}$، إذن {answer}.",
        ),
        "K",
        {"type": "roots", "f": f, "roots": (r1, r2)},
        wrong_kinds=kinds,
    )


@variant("2.1", G10, example=2)
def solutions_from_table(rng: random.Random) -> Problem:
    r1 = rng.randint(-4, 3)
    r2 = r1 + rng.randint(1, 4)
    f = sp.expand(rng.choice([1, -1]) * (x - r1) * (x - r2))
    low, high = r1 - 1, r2 + 1
    table = "، ".join(f"$f({px})={f.subs(x, px)}$" for px in range(low, high + 1))
    answer = solutions(r1, r2)
    wrong, kinds = tagged_wrongs(
        answer,
        ("concept", solutions(low, high)),
        ("partial", solutions(r1)),
        ("partial", solutions(r2)),
        ("sign", solutions(-r1, -r2)),
        ("concept", f"$x={f.subs(x, 0)}$"),
    )
    return Problem(
        "2.1",
        f"أُنشئ جدول قيم للدالة $f(x)={tex(f)}$، فكانت: {table}. ما حلول المعادلة ${tex(f)}=0$؟",
        answer,
        wrong,
        (
            "حلول المعادلة هي قيم $x$ التي تكون عندها $f(x)=0$.",
            f"من الجدول: $f({r1})=0$ و$f({r2})=0$، إذن {answer}.",
        ),
        "K",
        {"type": "roots", "f": f, "roots": (r1, r2)},
        wrong_kinds=kinds,
    )


@variant("2.1", G10, example=1)
def number_of_solutions_from_vertex(rng: random.Random) -> Problem:
    count, up, h = rng.choice([0, 1, 2]), rng.random() < 0.5, rng.randint(-6, 6)
    size = rng.randint(1, 9)
    k = 0 if count == 1 else (-size if up == (count == 2) else size)
    direction = UP if up else DOWN
    side = "تحت" if k < 0 else "فوق"
    reason = {
        0: f"الرأس يقع {side} المحور $x$ والقطع المكافئ يفتح إلى {direction}، فلا يقطع التمثيل البياني "
        "المحور $x$.",
        1: "الرأس يقع على المحور $x$، فيمسّ التمثيل البياني المحور $x$ عند الرأس وحده.",
        2: f"الرأس يقع {side} المحور $x$ والقطع المكافئ يفتح إلى {direction}، فيقطع التمثيل البياني "
        "المحور $x$ في نقطتين.",
    }[count]
    answer = COUNTS[count]
    wrong, kinds = tagged_wrongs(
        answer,
        *[("concept", text) for n, text in COUNTS.items() if n != count],
        ("concept", "عدد لا نهائي من الحلول"),
    )
    return Problem(
        "2.1",
        f"رأس القطع المكافئ الذي يمثّل الدالة التربيعية $f$ هو النقطة $({h},{k})$، ويفتح القطع إلى "
        f"{direction}. كم حلًّا حقيقيًّا للمعادلة $f(x)=0$؟",
        answer,
        wrong,
        (reason, f"إذن {COUNT_PHRASES[count]}."),
        "A",
        {"type": "solution_count", "f": (1 if up else -1) * (x - h) ** 2 + k, "count": count},
        wrong_kinds=kinds,
    )


def between(low: int) -> str:
    return f"بين ${low}$ و${low + 1}$"


@variant("2.1", G10, example=2)
def solution_between_consecutive_integers(rng: random.Random) -> Problem:
    h, d = rng.randint(-3, 3), rng.choice([2, 3, 5, 6, 7, 8, 10, 11, 12, 13])
    f = sp.expand((x - h) ** 2 - d)
    low = h + math.isqrt(d)
    table = "، ".join(f"$f({px})={f.subs(x, px)}$" for px in range(low - 1, low + 3))
    answer = between(low)
    return Problem(
        "2.1",
        f"أُنشئ جدول قيم للدالة $f(x)={tex(f)}$، فكانت: {table}. بين أيّ عددين صحيحين متتاليين "
        f"يقع حل للمعادلة ${tex(f)}=0$؟",
        answer,
        (between(low - 1), between(low + 1), between(low - 2)),
        (
            "يقع حل المعادلة بين قيمتين متتاليتين للمتغير $x$ تتغير بينهما إشارة $f(x)$.",
            f"$f({low})={f.subs(x, low)}$ سالبة و$f({low + 1})={f.subs(x, low + 1)}$ موجبة، "
            f"فالحل يقع {answer}.",
        ),
        "A",
        {"type": "sign_change", "f": f, "low": low, "high": low + 1},
        wrong_kinds=("nearby", "nearby", "nearby"),
    )


@variant("2.1", G10, example=3)
def approximate_landing_time(rng: random.Random) -> Problem:
    f, v, s, _, low, high = projectile(rng)
    answer = seconds(high)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", seconds(-low)),
        ("formula", seconds(high - low)),
        ("coefficient", seconds(v / 10)),
        ("coefficient", seconds(s)),
        ("formula", seconds(high / 2)),
    )
    return Problem(
        "2.1",
        "رُميت كرة إلى الأعلى، ويُعطى ارتفاعها بالأمتار بعد $x$ من الثواني بالدالة "
        f"$f(x)={tex(f)}$. يقطع التمثيل البياني للدالة المحور $x$ عند $x\\approx{tenth(low)}$ "
        f"و$x\\approx{tenth(high)}$. بعد كم ثانية تقريبًا تصل الكرة إلى الأرض؟",
        answer,
        wrong,
        (
            "تصل الكرة إلى الأرض عندما يكون ارتفاعها صفرًا، أي عند حل موجب للمعادلة $f(x)=0$.",
            f"الحل $x\\approx{tenth(low)}$ سالب فلا يمثّل زمنًا، إذن تصل الكرة إلى الأرض بعد "
            f"${tenth(high)}$ ثانية تقريبًا.",
        ),
        "K",
        {"type": "approx_root", "f": f, "value": float(tenth(high))},
        wrong_kinds=kinds,
    )


# «اكتشف الخطأ» في الحل بجدول القيم: الزلّة → (رقم الخطوة التي تقع فيها، نوع الخطأ من ERROR_KINDS).
TABLE_SLIPS = {
    "moved_sign": (1, "sign"),  # نقل الطرف الأيمن دون تغيير إشارته
    "linear_sign": (2, "sign"),  # عكس إشارة الحد الخطي في الدالة المرتبطة
    "target_value": (3, "coefficient"),  # بحث في الجدول عن الطرف الأيمن المعطى بدل الصفر
    "single_zero": (3, "partial"),  # اكتفى بأول صفر في الجدول
}


def table_chain(r1: int, r2: int, k: int, shift: int, slip: str | None = None) -> Chain:
    """خطوات حل x²+bx+c+k=k (جذراه r1<r2) بجدول قيم الدالة المرتبطة، كل خطوة نصها ومعادلتها (عبارة = 0).

    slip زلّة واحدة تُزرع في خطوتها وتُبنى عليها الخطوات التالية بلا خطأ آخر؛ None الحل الصحيح.
    shift إزاحة الجذرين نحو بعضهما التي تحدثها زلّة تغيّر الحد الثابت (k مختار ليبقيا صحيحين).
    """
    b, c = -(r1 + r2), r1 * r2
    standard = x**2 + b * x + c + (2 * k if slip == "moved_sign" else 0)
    related = standard.subs(x, -x) if slip == "linear_sign" else standard
    target = k if slip == "target_value" else 0
    if slip in ("moved_sign", "target_value"):
        zeros = (r1 + shift, r2 - shift)
    elif slip == "linear_sign":
        zeros = (-r2, -r1)
    else:
        zeros = (r1, r2)
    found = zeros[:1] if slip == "single_zero" else zeros
    shown = zeros if slip == "linear_sign" else (*zeros, r1, r2)
    table = "، ".join(f"$f({px})={related.subs(x, px)}$" for px in range(min(shown) - 1, max(shown) + 2))
    return [
        (f"نجعل أحد طرفي المعادلة صفرًا: ${tex(standard)}=0$", standard),
        (f"نكوّن جدول قيم للدالة المرتبطة $f(x)={tex(related)}$: {table}", related),
        (
            f"حلول المعادلة قيم $x$ التي تجعل $f(x)={target}$، وهي من الجدول: {solutions(*found)}",
            sp.Mul(*[x - zero for zero in found]),
        ),
    ]


@variant("2.1", G10, example=2, registry=ERROR_SPOTTING)
def spot_error_in_solving_by_table(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(TABLE_SLIPS))
    while True:
        r1, gap, shift = rng.randint(-6, 3), rng.randint(1, 5), rng.choice([-1, 1, 2])
        r2, free = r1 + gap, nz(rng, -6, 6)
        # الزلّة التي تغيّر الحد الثابت تغيّره بمقدار يبقي الجذرين صحيحين: r1+shift وr2-shift
        change = shift * (gap - shift)
        k = {"moved_sign": change // 2, "target_value": -change}.get(slip, free)
        whole = slip != "moved_sign" or change % 2 == 0
        if k and whole and r1 + r2 and gap > 2 * shift:
            break
    f = sp.expand((x - r1) * (x - r2))
    return spotted_chain(
        "2.1",
        f"حلّ طالب المعادلة ${tex(f + k)}={k}$ باستعمال جدول قيم {SPOT_TASK}",
        (table_chain(r1, r2, k, shift, slip), table_chain(r1, r2, k, shift)),
        TABLE_SLIPS[slip],
        solutions(r1, r2),
        f,
        (r1, r2),
    )


# الدرس 2.2: حل المعادلات التربيعية بالتحليل إلى العوامل
@variant("2.2", G10, example=1)
def zero_product_property(rng: random.Random) -> Problem:
    if rng.random() < 0.5:
        r1, r2 = two_roots(rng, -9, 9)
        left, factors = product(r1, r2), (linear(r1), linear(r2))
    else:
        p, r2 = rng.choice([2, 3, 4, 5]), nz(rng, -7, 7)
        q = rng.choice([n for n in range(-9, 10) if n and math.gcd(p, abs(n)) == 1])
        r1 = sp.Rational(-q, p)
        left, factors = f"({p}x{q:+d}){shifted(r2)}", (f"{p}x{q:+d}", linear(r2))
    answer = solutions(r1, r2)
    wrong, kinds = solution_wrongs(answer, r1, r2)
    return Problem(
        "2.2",
        f"حلّ المعادلة ${left}=0$ باستعمال خاصية ناتج الضرب الصفري.",
        answer,
        wrong,
        (f"بخاصية ناتج الضرب الصفري: ${factors[0]}=0$ أو ${factors[1]}=0$", f"إذن {answer}."),
        "K",
        {"type": "roots", "f": sp.expand((x - r1) * (x - r2)), "roots": (r1, r2)},
        wrong_kinds=kinds,
    )


@variant("2.2", G10, example=2)
def solve_trinomial_by_factoring(rng: random.Random) -> Problem:
    while True:
        r1, r2 = two_roots(rng, -9, 9, zero=False)
        if r1 + r2:
            break
    f = sp.expand((x - r1) * (x - r2))
    answer = solutions(r1, r2)
    wrong, kinds = solution_wrongs(answer, r1, r2)
    return Problem(
        "2.2",
        f"حلّ المعادلة ${tex(f)}=0$ بالتحليل إلى العوامل.",
        answer,
        wrong,
        (
            f"نحلّل ثلاثية الحدود: ${product(r1, r2)}=0$",
            f"بخاصية ناتج الضرب الصفري: ${linear(r1)}=0$ أو ${linear(r2)}=0$",
            f"إذن {answer}.",
        ),
        "K",
        {"type": "roots", "f": f, "roots": (r1, r2)},
        wrong_kinds=kinds,
    )


@variant("2.2", G10, example=2)
def solve_rearranged_equation_by_factoring(rng: random.Random) -> Problem:
    p, r = rng.choice([2, 3]), nz(rng, -6, 6)
    q = rng.choice([n for n in range(-7, 8) if n and math.gcd(p, abs(n)) == 1])
    other = sp.Rational(-q, p)
    f = sp.expand((p * x + q) * (x - r))
    answer = solutions(other, r)
    wrong, kinds = solution_wrongs(answer, other, r)
    return Problem(
        "2.2",
        f"حلّ المعادلة ${tex(f + q * r)}={q * r}$ بالتحليل إلى العوامل.",
        answer,
        wrong,
        (
            f"نكتب المعادلة في الصيغة القياسية: ${tex(f)}=0$",
            f"نحلّل ثلاثية الحدود: $({p}x{q:+d}){shifted(r)}=0$",
            f"بخاصية ناتج الضرب الصفري: ${p}x{q:+d}=0$ أو ${linear(r)}=0$",
            f"إذن {answer}.",
        ),
        "A",
        {"type": "roots", "f": f, "roots": (other, r)},
        wrong_kinds=kinds,
    )


@variant("2.2", G10, example=3)
def rectangle_dimensions_by_factoring(rng: random.Random) -> Problem:
    thing = rng.choice(["حديقة", "قاعة", "ساحة", "قطعة أرض"])
    width, extra = rng.randint(3, 12), rng.randint(1, 8)
    length, area = width + extra, width * (width + extra)

    def text(w: int, long: int) -> str:
        return f"العرض ${w}$ والطول ${long}$ (بالأمتار)"

    answer = text(width, length)
    return Problem(
        "2.2",
        f"{thing} مستطيلة الشكل يزيد طولها على عرضها بمقدار ${extra}$ من الأمتار، ومساحتها ${area}$ "
        "من الأمتار المربعة. أوجد بُعديها.",
        answer,
        (text(width - 1, length - 1), text(width + 1, length + 1), text(width, length + extra)),
        (
            f"نفرض العرض $x$، فيكون الطول $x+{extra}$، والمساحة $x(x+{extra})={area}$",
            f"${tex(x**2 + extra * x - area)}=0$",
            f"${product(width, -length)}=0$، إذن $x={width}$ أو $x={-length}$",
            f"العرض لا يكون سالبًا، إذن {answer}.",
        ),
        "A",
        {"type": "rectangle", "width": width, "length": length, "extra": extra, "area": area},
        wrong_kinds=("nearby", "nearby", "formula"),
    )


@variant("2.2", G10, example=4)
def intercepts_and_axis_from_factored_form(rng: random.Random) -> Problem:
    while True:
        p, q = two_roots(rng, -8, 8)
        if (p + q) % 2 == 0:
            break
    a, h = rng.choice([-2, -1, 1, 2]), (p + q) // 2

    def text(first: int, second: int, axis: int) -> str:
        return f"المقطعان $x$ هما ${first}$ و${second}$، ومحور التماثل $x={axis}$"

    answer = text(p, q, h)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", text(-q, -p, -h)),
        ("formula", text(p, q, p + q)),
        ("formula", text(p, q, q - p)),
        ("nearby", text(p - 1, q - 1, h - 1)),
        ("nearby", text(p, q, h + 1)),
        ("nearby", text(p, q, h - 1)),
    )
    return Problem(
        "2.2",
        f"أوجد المقطعين $x$ ومعادلة محور التماثل للتمثيل البياني للدالة $f(x)={lead(a)}{product(p, q)}$.",
        answer,
        wrong,
        (
            f"المقطعان $x$ هما صفرا الدالة: $x={p}$ و$x={q}$.",
            f"محور التماثل يمرّ بمنتصف المسافة بين المقطعين: $x=\\dfrac{{{plus(p, q)}}}{{2}}={h}$",
        ),
        "K",
        {"type": "factored_axis", "f": sp.expand(a * (x - p) * (x - q)), "roots": (p, q), "axis": h},
        wrong_kinds=kinds,
    )


@variant("2.2", G10, example=5)
def factored_form_from_intercepts_and_point(rng: random.Random) -> Problem:
    p, q = two_roots(rng, -6, 6)
    a = rng.choice([-3, -2, -1, 2, 3])
    s = rng.choice([n for n in range(-7, 8) if n not in (p, q)])
    t = a * (s - p) * (s - q)

    def rule(lead_a: int, first: int, second: int) -> str:
        return f"$f(x)={lead(lead_a)}{product(*sorted((first, second)))}$"

    answer = rule(a, p, q)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", rule(a, -p, -q)),
        ("sign", rule(-a, p, q)),
        ("coefficient", rule(1, p, q)),
        ("sign", rule(-a, -p, -q)),
        ("coefficient", rule(2 * a, p, q)),
        ("coefficient", rule(3 * a, p, q)),
    )
    return Problem(
        "2.2",
        f"يقطع قطع مكافئ المحور $x$ عند $x={p}$ و$x={q}$، ويمرّ بالنقطة $({s},{t})$. "
        "اكتب قاعدة الدالة التربيعية التي تمثّله في الصيغة التحليلية.",
        answer,
        wrong,
        (
            f"المقطعان $x$ هما ${p}$ و${q}$، فالصيغة التحليلية $f(x)=a{product(p, q)}$",
            f"نعوّض النقطة $({s},{t})$: ${t}=a({minus(s, p)})({minus(s, q)})$",
            f"${t}={(s - p) * (s - q)}a$، إذن $a={a}$",
        ),
        "A",
        {"type": "factored_point", "f": sp.expand(a * (x - p) * (x - q)), "roots": (p, q), "point": (s, t)},
        wrong_kinds=kinds,
    )


# «اكتشف الخطأ» في الحل بالتحليل إلى العوامل: الزلّة → (رقم الخطوة التي تقع فيها، نوع الخطأ من ERROR_KINDS).
FACTORING_SLIPS = {
    "factor_sign": (2, "sign"),  # عكس إشارتي العددين داخل العاملين
    "single_factor": (3, "partial"),  # ساوى عاملًا واحدًا بالصفر
    "inverted": (4, "swap"),  # قلب الكسر عند حل المعادلة الخطية
    "undivided": (4, "formula"),  # لم يقسم على معامل x
}


def factoring_chain(p: int, q: int, r: int, slip: str | None = None) -> Chain:
    """خطوات حل (px+q)(x-r)=0 المعطاة بطرف أيمن غير صفري، كل خطوة نصها ومعادلتها (عبارة = 0).

    slip زلّة واحدة تُزرع في خطوتها وتُبنى عليها الخطوات التالية بلا خطأ آخر؛ None الحل الصحيح.
    """
    f = sp.expand((p * x + q) * (x - r))
    fq, fr = (-q, -r) if slip == "factor_sign" else (q, r)
    factored = (p * x + fq) * (x - fr)
    if slip == "inverted":
        first = sp.Rational(-p, fq)
    elif slip == "undivided":
        first = sp.Integer(-fq)
    else:
        first = sp.Rational(-fq, p)
    if slip == "single_factor":
        zeroed, third, found = f"${p}x{fq:+d}=0$", p * x + fq, (first,)
    else:
        zeroed, third, found = f"${p}x{fq:+d}=0$ أو ${linear(fr)}=0$", factored, (first, fr)
    return [
        (f"نكتب المعادلة في الصيغة القياسية: ${tex(f)}=0$", f),
        (f"نحلّل ثلاثية الحدود: $({p}x{fq:+d}){shifted(fr)}=0$", factored),
        (f"بخاصية ناتج الضرب الصفري: {zeroed}", third),
        (f"إذن {solutions(*found)}", sp.Mul(*[x - value for value in found])),
    ]


@variant("2.2", G10, example=2, registry=ERROR_SPOTTING)
def spot_error_in_solving_by_factoring(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(FACTORING_SLIPS))
    while True:
        p, r = rng.choice([2, 3, 5]), nz(rng, -6, 6)
        # |q|>1 وأولي مع p: الحل الكسري لا يصير صحيحًا بقلبه؛ وq≠-r ليبقى الحلّان بعد ترك القسمة مختلفين
        q = rng.choice([n for n in range(-7, 8) if abs(n) > 1 and math.gcd(p, abs(n)) == 1])
        if q != -r:
            break
    f = sp.expand((p * x + q) * (x - r))
    other = sp.Rational(-q, p)
    return spotted_chain(
        "2.2",
        f"حلّ طالب المعادلة ${tex(f + q * r)}={q * r}$ بالتحليل إلى العوامل {SPOT_TASK}",
        (factoring_chain(p, q, r, slip), factoring_chain(p, q, r)),
        FACTORING_SLIPS[slip],
        solutions(other, r),
        f,
        (other, r),
    )


# الدرس 2.3: إعادة كتابة المقادير الجذرية
@variant("2.3", G10, example=1)
def simplify_square_root(rng: random.Random) -> Problem:
    k, free = rng.randint(2, 9), rng.choice(SQUARE_FREE)
    n = k * k * free
    wrong, kinds = tagged_wrongs(
        m(root(k, free)),
        ("square", m(root(k * k, free))),
        ("swap", m(root(free, k))),
        ("formula", m(root(k, k * free))),
        ("nearby", m(root(k + 1, free))),
    )
    return Problem(
        "2.3",
        f"اكتب $\\sqrt{{{n}}}$ في أبسط صورة.",
        m(root(k, free)),
        wrong,
        (
            f"أكبر عامل مربع كامل للعدد ${n}$ هو ${k * k}$: $\\sqrt{{{n}}}=\\sqrt{{{k * k}\\cdot{free}}}$",
            f"$\\sqrt{{{k * k}}}\\cdot\\sqrt{{{free}}}={root(k, free)}$",
        ),
        "K",
        {"type": "radical", "square": sp.Integer(n), "coefficient": sp.Integer(k), "radicand": free},
        wrong_kinds=kinds,
    )


@variant("2.3", G10, example=2)
def simplify_multiple_of_square_root(rng: random.Random) -> Problem:
    c, k, free = rng.randint(2, 6), rng.randint(2, 5), rng.choice(SQUARE_FREE)
    n = k * k * free
    answer = m(root(c * k, free))
    wrong, kinds = tagged_wrongs(
        answer,
        ("formula", m(root(c + k, free))),
        ("square", m(root(c * k * k, free))),
        ("partial", m(root(c, free))),
        ("nearby", m(root(c * k + 1, free))),
    )
    return Problem(
        "2.3",
        f"اكتب ${root(c, n)}$ في أبسط صورة.",
        answer,
        wrong,
        (
            f"$\\sqrt{{{n}}}=\\sqrt{{{k * k}\\cdot{free}}}={root(k, free)}$",
            f"${root(c, n)}={c}\\cdot{root(k, free)}={root(c * k, free)}$",
        ),
        "K",
        {
            "type": "radical",
            "square": sp.Integer(c * c * n),
            "coefficient": sp.Integer(c * k),
            "radicand": free,
        },
        wrong_kinds=kinds,
    )


@variant("2.3", G10, example=3)
def simplify_square_root_with_variable(rng: random.Random) -> Problem:
    k, free, p = rng.randint(2, 5), rng.choice([2, 3, 5, 6, 7]), rng.randint(2, 7)
    n, half, odd = k * k * free, p // 2, p % 2

    def text(coefficient: int, power: int, with_x: int) -> str:
        variable = "x" if power == 1 else f"x^{{{power}}}"
        return m(f"{coefficient}{variable}\\sqrt{{{free}{'x' if with_x else ''}}}")

    answer = text(k, half, odd)
    even = f"x^{{{2 * half}}}"
    wrong = (
        text(k, half, 1 - odd),
        text(k * k, half, odd),
        text(k, p, odd),
    )
    kinds = (
        "partial",
        "square",
        "formula",
    )
    return Problem(
        "2.3",
        f"اكتب $\\sqrt{{{n}x^{{{p}}}}}$ في أبسط صورة، حيث $x\\geq 0$.",
        answer,
        wrong,
        (
            "نكتب المجذور بدلالة عوامل مربعة كاملة: "
            f"$\\sqrt{{{n}x^{{{p}}}}}=\\sqrt{{{k * k}\\cdot {even}\\cdot {free}{'x' if odd else ''}}}$",
            f"$\\sqrt{{{k * k}}}\\cdot\\sqrt{{{even}}}\\cdot\\sqrt{{{free}{'x' if odd else ''}}}="
            f"{answer[1:-1]}$",
        ),
        "A",
        {"type": "radical", "square": n * x**p, "coefficient": k * x**half, "radicand": free * x**odd},
        wrong_kinds=kinds,
    )


@variant("2.3", G10, example=4)
def multiply_radical_expressions(rng: random.Random) -> Problem:
    g = rng.choice([2, 3, 5])
    u, v = rng.sample([n for n in (1, 2, 3, 5, 7) if n != g], 2)
    a, b = rng.randint(1, 5), rng.randint(1, 5)
    first, second, outer = g * u, g * v, a * b
    answer = m(root(outer * g, u * v))
    split = f"{g * g}\\cdot{u * v}"
    wrong, kinds = tagged_wrongs(
        answer,
        ("partial", m(root(outer, u * v))),
        ("square", m(root(outer * g * g, u * v))),
        ("formula", m(root((a + b) * g, u * v))),
        ("formula", m(root(outer * g, u * v * g))),
    )
    return Problem(
        "2.3",
        f"أوجد ناتج الضرب في أبسط صورة: ${root(a, first)}\\cdot{root(b, second)}$",
        answer,
        wrong,
        (
            "نضرب المعاملين معًا والمجذورين معًا: "
            f"${root(a, first)}\\cdot{root(b, second)}={root(outer, first * second)}$",
            f"${root(outer, first * second)}={root(outer, split)}={root(outer * g, u * v)}$",
        ),
        "A",
        {
            "type": "radical",
            "square": sp.Integer(outer * outer * first * second),
            "coefficient": sp.Integer(outer * g),
            "radicand": u * v,
        },
        wrong_kinds=kinds,
    )


# «اكتشف الخطأ» في تبسيط مضاعف جذر: الزلّة → (رقم الخطوة التي تقع فيها، نوع الخطأ من ERROR_KINDS).
RADICAL_SLIPS = {
    "unrooted": (2, "square"),  # أخرج العامل المربع الكامل من الجذر دون أخذ جذره
    "halved": (2, "formula"),  # نصّف العامل المربع الكامل بدل أخذ جذره
    "added": (3, "formula"),  # جمع الناتج والمعامل بدل ضربهما
    "swapped": (4, "swap"),  # بدّل المعامل والمجذور
}


def radical_item(c: int, k: int, free: int, slip: str) -> ErrorSpotting | None:
    step, kind = RADICAL_SLIPS[slip]
    n = k * k * free
    rules: tuple[Rule, ...] = ((k * k, free), (sp.sqrt(ref(1)),), (c * ref(2),), (ref(3), ref(1, 1)))
    wrong: Rule = {
        "unrooted": (ref(1),),
        "halved": (ref(1) / 2,),
        "added": (c + ref(2),),
        "swapped": (ref(1, 1), ref(3)),
    }[slip]
    if slip == "halved" and k % 2:  # نصف مربع عدد فردي ليس عددًا صحيحًا
        return None

    def texts(rows: list[Row], slipped: bool) -> tuple[str, ...]:
        (square, rest), (rooted,), (coefficient,), (outside, inside) = rows
        split = f"{square}\\cdot{rest}"
        working = f"{c}+{rooted}" if slipped and slip == "added" else f"{c}\\cdot{rooted}"
        return (
            f"نكتب المجذور بدلالة أكبر عامل مربع كامل: ${root(c, n)}={root(c, split)}$",
            f"نوجد الجذر التربيعي للعامل المربع الكامل: $\\sqrt{{{square}}}={rooted}$",
            f"نضرب الناتج في المعامل: ${working}={coefficient}$",
            f"إذن ${root(c, n)}={root(outside, inside)}$",
        )

    return spotted_values(
        "2.3",
        f"كتب طالب ${root(c, n)}$ في أبسط صورة {SPOT_TASK}",
        rules,
        (step, kind, wrong),
        texts,
        m(root(c * k, free)),
        {"quantity": "simplified_radical", "square": sp.Integer(c * c * n)},
    )


@variant("2.3", G10, example=2, registry=ERROR_SPOTTING)
def spot_error_in_simplifying_radical(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(RADICAL_SLIPS))
    while True:
        item = radical_item(rng.randint(2, 6), rng.randint(2, 5), rng.choice(SQUARE_FREE), slip)
        if item is not None:
            return item


def diagonal_rectangles() -> list[tuple[int, int, int, int]]:
    """(العرض، الطول، k، m) لمستطيلات قطرها k√m بعامل مربع كامل يُخرَج من الجذر."""
    rows = []
    for width in range(1, 13):
        for length in range(width + 1, 13):
            n = width * width + length * length
            k = max(d for d in range(1, math.isqrt(n) + 1) if n % (d * d) == 0)
            if k > 1 and n // (k * k) > 1:
                rows.append((width, length, k, n // (k * k)))
    return rows


DIAGONAL_RECTANGLES = diagonal_rectangles()


@variant("2.3", G10, example=5)
def rectangle_diagonal_as_radical(rng: random.Random) -> Problem:
    thing, unit = rng.choice(
        [("لوحة", "بالسنتيمترات"), ("بطاقة", "بالسنتيمترات"), ("حديقة", "بالأمتار"), ("ساحة", "بالأمتار")]
    )
    width, length, k, free = rng.choice(DIAGONAL_RECTANGLES)
    n = width * width + length * length
    answer = m(root(k, free))
    wrong, kinds = tagged_wrongs(
        answer,
        ("formula", m(width + length)),
        ("square", m(root(k * k, free))),
        ("nearby", m(root(k + 1, free))),
        ("nearby", m(root(k, free + 1))),
    )
    return Problem(
        "2.3",
        f"{thing} مستطيلة الشكل طولها ${length}$ وعرضها ${width}$ {unit}. اكتب طول قطرها في أبسط صورة جذرية.",
        answer,
        wrong,
        (
            f"بنظرية فيثاغورس طول القطر $\\sqrt{{{length}^2+{width}^2}}=\\sqrt{{{n}}}$",
            f"$\\sqrt{{{n}}}=\\sqrt{{{k * k}\\cdot{free}}}={root(k, free)}$",
        ),
        "A",
        {
            "type": "radical",
            "square": sp.Integer(length) ** 2 + sp.Integer(width) ** 2,
            "coefficient": sp.Integer(k),
            "radicand": free,
        },
        wrong_kinds=kinds,
    )


# الدرس 2.5: إكمال المربع. المثال 5 (صيغة الرأس بمعامل رئيس غير الواحد) إثرائي، فصيغة الرأس هنا بمعامل واحد.
def binomial(b: int) -> str:
    """ثنائية الحد x+b/2 بين قوسين."""
    if b % 2 == 0:
        return f"(x{b // 2:+d})"
    return f"\\left(x{'+' if b > 0 else '-'}\\dfrac{{{abs(b)}}}{{2}}\\right)"


@variant("2.5", G10, example=1)
def constant_completing_the_square(rng: random.Random) -> Problem:
    b = rng.choice([*range(2, 21, 2), 3, 5, 7, 9]) * rng.choice([1, -1])
    c = sp.Rational(b, 2) ** 2
    wrong, kinds = tagged_wrongs(
        c,
        ("square", sp.Rational(b, 2)),
        ("formula", sp.Integer(b * b)),
        ("formula", sp.Rational(b * b, 2)),
        ("formula", sp.Integer(2 * b)),
    )
    return Problem(
        "2.5",
        f"أوجد قيمة $c$ التي تجعل $x^2{b:+d}x+c$ ثلاثية حدود في صورة مربع كامل.",
        m(c),
        wrong,
        (
            f"نضيف مربع نصف معامل $x$: $c=\\left(\\dfrac{{{b}}}{{2}}\\right)^2={tex(c)}$",
            f"ثلاثية الحدود $x^2{b:+d}x+{tex(c)}$ تساوي ${binomial(b)}^2$.",
        ),
        "K",
        {"type": "perfect_square", "b": b, "c": c},
        wrong_kinds=kinds,
    )


@variant("2.5", G10, example=1)
def perfect_square_trinomial_as_binomial_square(rng: random.Random) -> Problem:
    h = nz(rng, -10, 10)
    b, c = 2 * h, h * h
    answer = f"${binomial(b)}^2$"
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", f"$(x{-h:+d})^2$"),
        ("coefficient", f"$(x{b:+d})^2$"),
        ("concept", f"$(x{h:+d})(x{-h:+d})$"),
        ("coefficient", f"$(x{c:+d})^2$"),
    )
    return Problem(
        "2.5",
        f"اكتب ثلاثية الحدود $x^2{b:+d}x+{c}$ في صورة مربع ثنائية حد.",
        answer,
        wrong,
        (
            f"نصف معامل $x$ هو ${h}$، ومربعه ${c}$ يساوي الحد الثابت.",
            f"إذن $x^2{b:+d}x+{c}={binomial(b)}^2$.",
        ),
        "K",
        {"type": "perfect_square", "b": b, "c": c},
        wrong_kinds=kinds,
    )


def surd_solutions(center: int, radicand: int) -> str:
    return f"$x={center}\\pm\\sqrt{{{radicand}}}$"


def completing_steps(h: int, d: int) -> tuple[str, str, str]:
    """خطوات إكمال المربع للمعادلة x²-2hx+h²-d=0 بعد أن يصير معامل x² واحدًا."""
    b, c = -2 * h, h * h - d
    return (
        f"ننقل الحد الثابت إلى الطرف الأيمن ونضيف $\\left(\\dfrac{{{b}}}{{2}}\\right)^2={h * h}$ "
        f"إلى الطرفين: $x^2{b:+d}x+{h * h}={-c}+{h * h}$",
        f"${shifted(h)}^2={d}$",
        f"${linear(h)}=\\pm\\sqrt{{{d}}}$، إذن {surd_solutions(h, d)}",
    )


@variant("2.5", G10, example=2)
def solve_by_completing_the_square(rng: random.Random) -> Problem:
    h, d = nz(rng, -6, 6), rng.choice(SQUARE_FREE)
    f = sp.expand((x - h) ** 2 - d)
    answer = surd_solutions(h, d)
    wrong = (
        surd_solutions(-h, d),
        f"$x={h}\\pm{d}$",
        surd_solutions(h, d + h * h),
    )
    kinds = (
        "sign",
        "formula",
        "partial",
    )
    return Problem(
        "2.5",
        f"حلّ المعادلة ${tex(f)}=0$ بإكمال المربع.",
        answer,
        wrong,
        completing_steps(h, d),
        "A",
        {"type": "roots", "f": f, "roots": (h + sp.sqrt(d), h - sp.sqrt(d))},
        wrong_kinds=kinds,
    )


# «اكتشف الخطأ» في إكمال المربع: الزلّة → (رقم الخطوة التي تقع فيها، نوع الخطأ من ERROR_KINDS).
COMPLETING_SLIPS = {
    "moved_sign": (1, "sign"),  # نقل الحد الثابت دون تغيير إشارته
    "unsquared_half": (2, "square"),  # أضاف إلى الطرف الأيمن نصف معامل x بلا تربيع
    "binomial_sign": (3, "sign"),  # عكس إشارة العدد داخل القوس
    "single_root": (4, "partial"),  # أخذ الجذر الموجب وحده
    "no_root": (4, "formula"),  # لم يأخذ جذر الطرف الأيمن
    "center_sign": (5, "sign"),  # نقل العدد إلى الطرف الأيمن دون تغيير إشارته
}
SPOTTING_RADICANDS = (1, 4, 9, 16, *SQUARE_FREE)


def clean_radicand(n: int) -> bool:
    """موجب، ومربع كامل أو بلا عامل مربع: جذره عدد صحيح أو جذر لا يُبسَّط."""
    return n > 0 and (math.isqrt(n) ** 2 == n or square_free(n))


def root_text(n: int) -> str:
    whole = math.isqrt(n)
    return str(whole) if whole * whole == n else f"\\sqrt{{{n}}}"


def spread_solutions(center: int, radicand: int) -> str:
    """حلّا (x-center)²=radicand: عددان صحيحان إن كان المجذور مربعًا كاملًا، وإلا center±√radicand."""
    whole = math.isqrt(radicand)
    if whole * whole == radicand:
        return solutions(center - whole, center + whole)
    return surd_solutions(center, radicand)


def completing_chain(h: int, d: int, slip: str | None = None) -> list[tuple[str, sp.Expr]] | None:
    """خطوات حل x²-2hx+h²-d=0 بإكمال المربع، كل خطوة نصها ومعادلتها (عبارة = 0) من الأعداد نفسها.

    slip زلّة واحدة تُزرع في خطوتها وتُبنى عليها الخطوات التالية بلا خطأ آخر؛ None الحل الصحيح.
    يعيد None إن خرج الطرف الأيمن بعد الزلّة مجذورًا غير نظيف.
    """
    b, c = -2 * h, h * h - d
    moved = c if slip == "moved_sign" else -c
    added = -h if slip == "unsquared_half" else h * h
    right = moved + added
    if not clean_radicand(right):
        return None
    center = -h if slip == "binomial_sign" else h
    last = -center if slip == "center_sign" else center
    left = x**2 + b * x
    square = (x - center) ** 2
    if slip == "single_root":
        whole = math.isqrt(right)
        value = str(last + whole) if whole * whole == right else f"{last}+{root_text(right)}"
        side, fourth = root_text(right), x - center - sp.sqrt(right)
        final_text, final = f"$x={value}$", x - last - sp.sqrt(right)
    else:
        spread = right * right if slip == "no_root" else right
        side, fourth = f"\\pm {root_text(spread)}", square - spread
        final_text, final = spread_solutions(last, spread), (x - last) ** 2 - spread
    return [
        (f"ننقل الحد الثابت إلى الطرف الأيمن: $x^2{b:+d}x={moved}$", left - moved),
        (
            f"نضيف مربع نصف معامل $x$ إلى الطرفين: $x^2{b:+d}x+{h * h}={plus(moved, added)}$",
            left + h * h - right,
        ),
        (f"نكتب الطرف الأيسر في صورة مربع كامل: ${shifted(center)}^2={right}$", square - right),
        (f"نأخذ الجذر التربيعي للطرفين: ${linear(center)}={side}$", fourth),
        (f"إذن {final_text}", final),
    ]


@variant("2.5", G10, example=2, registry=ERROR_SPOTTING)
def spot_error_in_completing_the_square(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(COMPLETING_SLIPS))
    while True:
        h, d = nz(rng, -6, 6), rng.choice(SPOTTING_RADICANDS)
        shown = completing_chain(h, d, slip)
        # الزلّة يجب أن تغيّر الحلول: حد ثابت غير صفري، ونصف المعامل يخالف مربعه، والمجذور يخالف مربعه
        changes = (
            h * h != d and not (slip == "unsquared_half" and h == -1) and not (slip == "no_root" and d == 1)
        )
        if shown is not None and changes:
            break
    solved = completing_chain(h, d)
    if solved is None:  # المجذور d نظيف بالاختيار
        raise AssertionError((h, d))
    f = sp.expand((x - h) ** 2 - d)
    return spotted_chain(
        "2.5",
        f"حلّ طالب المعادلة ${tex(f)}=0$ بإكمال المربع {SPOT_TASK}",
        (shown, solved),
        COMPLETING_SLIPS[slip],
        spread_solutions(h, d),
        f,
        (h + sp.sqrt(d), h - sp.sqrt(d)),
    )


@variant("2.5", G10, example=3)
def solve_by_completing_the_square_with_leading_coefficient(rng: random.Random) -> Problem:
    a, h, d = rng.choice([2, 3, 4, 5]), nz(rng, -5, 5), rng.choice(SQUARE_FREE)
    monic = sp.expand((x - h) ** 2 - d)
    f = sp.expand(a * monic)
    answer = surd_solutions(h, d)
    wrong = (
        surd_solutions(-h, d),
        surd_solutions(h, a * d),
        f"$x={h}\\pm{d}$",
    )
    kinds = (
        "sign",
        "formula",
        "formula",
    )
    return Problem(
        "2.5",
        f"حلّ المعادلة ${tex(f)}=0$ بإكمال المربع.",
        answer,
        wrong,
        (f"نقسم الطرفين على ${a}$: ${tex(monic)}=0$", *completing_steps(h, d)),
        "A",
        {"type": "roots", "f": f, "roots": (h + sp.sqrt(d), h - sp.sqrt(d))},
        wrong_kinds=kinds,
    )


@variant("2.5", G10, example=4)
def vertex_form_by_completing_the_square(rng: random.Random) -> Problem:
    h, k = nz(rng, -6, 6), nz(rng, -9, 9)
    b, c = -2 * h, h * h + k
    f = x**2 + b * x + c

    def text(dh: int, dk: int, vertex: tuple[int, int]) -> str:
        return f"$f(x)={vertex_form(1, dh, dk)}$، والرأس $({vertex[0]},{vertex[1]})$"

    answer = text(h, k, (h, k))
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", text(-h, k, (-h, k))),
        ("sign", text(h, k, (-h, k))),
        ("coefficient", text(h, c, (h, c))),
        ("sign", text(h, -k, (h, -k))),
    )
    return Problem(
        "2.5",
        f"اكتب الدالة $f(x)={tex(f)}$ في صيغة الرأس بإكمال المربع، ثم حدّد رأس القطع المكافئ.",
        answer,
        wrong,
        (
            f"نضيف مربع نصف معامل $x$ ونطرحه: $f(x)=(x^2{b:+d}x+{h * h})-{h * h}{signed(c)}$",
            f"$f(x)={vertex_form(1, h, k)}$",
            f"الرأس $({h},{k})$.",
        ),
        "A",
        {"type": "vertex", "f": f, "vertex": (h, k)},
        wrong_kinds=kinds,
    )


# الدرس 2.6: القانون العام والمميز
def formula_values(a: int, b: int, c: int, disc: int) -> tuple[str, str]:
    return (
        f"$a={a}$، $b={b}$، $c={c}$",
        f"المميز: $b^2-4ac=({b})^2-4({a})({c})={disc}$",
    )


@variant("2.6", G10, example=2)
def quadratic_formula_rational_solutions(rng: random.Random) -> Problem:
    a, r = rng.choice([2, 3, 4]), nz(rng, -6, 6)
    q = rng.choice([n for n in range(-7, 8) if n and math.gcd(a, abs(n)) == 1])
    b, c = q - a * r, -q * r
    other, disc = sp.Rational(-q, a), (q + a * r) ** 2
    f = a * x**2 + b * x + c
    answer = solutions(other, r)
    wrong, kinds = solution_wrongs(answer, other, r)
    return Problem(
        "2.6",
        f"حلّ المعادلة ${tex(f)}=0$ باستعمال القانون العام.",
        answer,
        wrong,
        (
            *formula_values(a, b, c, disc),
            f"$x=\\dfrac{{-b\\pm\\sqrt{{b^2-4ac}}}}{{2a}}=\\dfrac{{{-b}\\pm{abs(q + a * r)}}}{{{2 * a}}}$",
            f"إذن {answer}.",
        ),
        "K",
        {"type": "roots", "f": f, "roots": (other, r)},
        wrong_kinds=kinds,
    )


@variant("2.6", G10, example=2)
def quadratic_formula_irrational_solutions(rng: random.Random) -> Problem:
    while True:
        a, b, c = rng.choice([1, 2, 3]), nz(rng, -9, 9), nz(rng, -9, 9)
        disc = b * b - 4 * a * c
        if disc > 1 and square_free(disc):
            break
    f = a * x**2 + b * x + c

    def text(top: int, under: str, bottom: int) -> str:
        return f"$x=\\dfrac{{{top}\\pm{under}}}{{{bottom}}}$"

    surd = f"\\sqrt{{{disc}}}"
    answer = text(-b, surd, 2 * a)
    wrong = (
        text(b, surd, 2 * a),
        text(-b, surd, a if a > 1 else 4),
        text(-b, str(disc), 2 * a),
    )
    kinds = (
        "sign",
        "formula",
        "formula",
    )
    return Problem(
        "2.6",
        f"حلّ المعادلة ${tex(f)}=0$ باستعمال القانون العام.",
        answer,
        wrong,
        (
            *formula_values(a, b, c, disc),
            f"$x=\\dfrac{{-b\\pm\\sqrt{{b^2-4ac}}}}{{2a}}=\\dfrac{{{-b}\\pm{surd}}}{{{2 * a}}}$",
        ),
        "A",
        {
            "type": "roots",
            "f": f,
            "roots": ((-b + sp.sqrt(disc)) / (2 * a), (-b - sp.sqrt(disc)) / (2 * a)),
        },
        wrong_kinds=kinds,
    )


def count_from(disc: int) -> int:
    return 2 if disc > 0 else (1 if disc == 0 else 0)


@variant("2.6", G10, example=4)
def discriminant_and_number_of_solutions(rng: random.Random) -> Problem:
    count = rng.choice([0, 1, 2])
    if count == 1:
        p, q, sign = rng.choice([1, 2, 3]), nz(rng, -5, 5), rng.choice([1, -1])
        a, b, c = sign * p * p, sign * 2 * p * q, sign * q * q
    else:
        while True:
            a, b, c = nz(rng, -3, 3), nz(rng, -8, 8), nz(rng, -9, 9)
            if count_from(b * b - 4 * a * c) == count:
                break
    disc, slip = b * b - 4 * a * c, b * b + 4 * a * c

    def text(value: int, n: int) -> str:
        return f"المميز ${value}$، و{COUNT_PHRASES[n]}"

    answer = text(disc, count)
    wrong = (
        text(disc, (count + 1) % 3),
        text(disc, (count + 2) % 3),
        text(slip, count_from(slip)),
    )
    kinds = (
        "concept",
        "concept",
        "formula",
    )
    return Problem(
        "2.6",
        f"أوجد قيمة المميز للمعادلة ${tex(a * x**2 + b * x + c)}=0$، ثم حدّد عدد حلولها الحقيقية.",
        answer,
        wrong,
        (
            *formula_values(a, b, c, disc),
            f"المميز {('سالب', 'يساوي صفرًا', 'موجب')[count]}، إذن {COUNT_PHRASES[count]}.",
        ),
        "K",
        {"type": "solution_count", "f": a * x**2 + b * x + c, "count": count, "discriminant": disc},
        wrong_kinds=kinds,
    )


# «اكتشف الخطأ» في المميز وعدد الحلول: الزلّة → (رقم الخطوة التي تقع فيها، نوع الخطأ من ERROR_KINDS).
DISCRIMINANT_SLIPS = {
    "moved_sign": (1, "sign"),  # نقل الطرف الأيمن دون تغيير إشارته
    "unsquared": (2, "square"),  # ضاعف b بدل تربيعه
    "negative_square": (2, "sign"),  # جعل مربع العدد السالب سالبًا
    "no_four": (3, "formula"),  # أسقط العامل 4
    "added": (4, "formula"),  # جمع بدل الطرح
    "reversed_count": (5, "concept"),  # عكس دلالة إشارة المميز على عدد الحلول
}
DISCRIMINANT_SIGNS = {-1: "سالب", 0: "يساوي صفرًا", 1: "موجب"}


def discriminant_item(a: int, b: int, c: int, slip: str) -> ErrorSpotting | None:
    """المعادلة ax²+bx=-c: الحد الثابت بعد النقل، ثم b² و4ac والمميز، ثم عدد الحلول من إشارته."""
    step, kind = DISCRIMINANT_SLIPS[slip]
    constant, square, product_4ac, value = ref(1), ref(2), ref(3), ref(4)
    rules: tuple[Rule, ...] = (
        (c,),
        (b * b,),
        (4 * a * constant,),
        (square - product_4ac,),
        (value, 1 + sp.sign(value)),
    )
    wrong: Rule = {
        "moved_sign": (-c,),
        "unsquared": (2 * b,),
        "negative_square": (-b * b,),
        "no_four": (a * constant,),
        "added": (square + product_4ac,),
        "reversed_count": (value, 1 - sp.sign(value)),
    }[slip]
    if slip == "negative_square" and b > 0:  # الزلّة في تربيع عدد سالب
        return None

    def texts(rows: list[Row], slipped: bool) -> tuple[str, ...]:
        (free,), (squared,), (four,), (disc,), (_, count) = (tuple(int(v) for v in row) for row in rows)
        factors = f"({a})({free})" if slipped and slip == "no_four" else f"4({a})({free})"
        combined = plus(squared, four) if slipped and slip == "added" else minus(squared, four)
        sign = DISCRIMINANT_SIGNS[(disc > 0) - (disc < 0)]
        return (
            f"نكتب المعادلة في الصيغة القياسية: ${tex(a * x**2 + b * x + free)}=0$، "
            f"فيكون $a={a}$ و$b={b}$ و$c={free}$",
            f"نحسب مربع $b$: $b^2=({b})^2={squared}$",
            f"نحسب $4ac$: $4ac={factors}={four}$",
            f"نحسب المميز: $b^2-4ac={combined}={disc}$",
            f"المميز {sign}، ف{COUNT_PHRASES[count]}",
        )

    disc = b * b - 4 * a * c
    return spotted_values(
        "2.6",
        f"حدّد طالب عدد الحلول الحقيقية للمعادلة ${tex(a * x**2 + b * x)}={-c}$ باستعمال المميز {SPOT_TASK}",
        rules,
        (step, kind, wrong),
        texts,
        f"المميز ${disc}$، و{COUNT_PHRASES[count_from(disc)]}",
        {"quantity": "discriminant_count", "f": a * x**2 + b * x + c},
    )


@variant("2.6", G10, example=4, registry=ERROR_SPOTTING)
def spot_error_in_discriminant(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(DISCRIMINANT_SLIPS))
    while True:
        item = discriminant_item(nz(rng, -3, 3), nz(rng, -8, 8), nz(rng, -9, 9), slip)
        if item is not None:
            return item


@variant("2.6", G10, example=4)
def constant_for_one_real_solution(rng: random.Random) -> Problem:
    a, b = rng.choice([1, 2, 3, 4]), 2 * nz(rng, -6, 6)
    k = sp.Rational(b * b, 4 * a)
    reduced = f"={tex(k)}" if math.gcd(b * b, 4 * a) > 1 else ""
    wrong, kinds = tagged_wrongs(
        k,
        ("formula", sp.Rational(b * b, a)),
        ("formula", sp.Rational(b * b, 2 * a)),
        ("formula", sp.Rational(b, 2 * a)),
        ("sign", -k),
    )
    return Problem(
        "2.6",
        f"أوجد قيمة $k$ التي تجعل للمعادلة ${lead(a)}x^2{b:+d}x+k=0$ حلًّا حقيقيًّا واحدًا.",
        m(k),
        wrong,
        (
            "للمعادلة حل حقيقي واحد عندما يساوي المميز صفرًا: $b^2-4ac=0$",
            f"$({b})^2-4({a})k=0$",
            f"${b * b}-{4 * a}k=0$، إذن $k={frac(b * b, 4 * a)}{reduced}$",
        ),
        "A",
        {"type": "solution_count", "f": a * x**2 + b * x + k, "count": 1},
        wrong_kinds=kinds,
    )


@variant("2.6", G10, example=3)
def landing_time_by_quadratic_formula(rng: random.Random) -> Problem:
    f, v, s, disc, low, high = projectile(rng)
    answer = seconds(high)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", seconds(-low)),
        ("formula", seconds(2 * high)),
        ("coefficient", seconds(v / 10)),
        ("coefficient", seconds(s)),
        ("formula", seconds(high - low)),
    )
    return Problem(
        "2.6",
        "قُذف جسم إلى الأعلى، ويُعطى ارتفاعه بالأمتار بعد $x$ من الثواني بالدالة "
        f"$f(x)={tex(f)}$. استعمل القانون العام لإيجاد الزمن الذي يصل عنده الجسم إلى الأرض، "
        "مقرّبًا الناتج إلى أقرب جزء من عشرة.",
        answer,
        wrong,
        (
            f"يصل الجسم إلى الأرض عندما $f(x)=0$، أي ${tex(f)}=0$",
            *formula_values(-5, v, s, disc),
            f"$x=\\dfrac{{{-v}\\pm\\sqrt{{{disc}}}}}{{-10}}$، أي $x\\approx{tenth(low)}$ أو "
            f"$x\\approx{tenth(high)}$",
            f"الزمن لا يكون سالبًا، إذن يصل الجسم إلى الأرض بعد ${tenth(high)}$ ثانية تقريبًا.",
        ),
        "A",
        {"type": "approx_root", "f": f, "value": float(tenth(high))},
        wrong_kinds=kinds,
    )


# الوحدة 2 (ب): المعادلات النسبية، والأنظمة الخطية-التربيعية، والمتباينات التربيعية، ومعادلة الدائرة
RATIOS = {2: "ضعف", 3: "ثلاثة أمثال", 4: "أربعة أمثال"}
# (ما تنجزه الآلتان معًا، اسم الآلة الواحدة، العمل المطلوب منها)
JOBS = (
    ("تملأ مضختان خزان ماء", "المضخة", "لملء الخزان"),
    ("تطبع طابعتان كتب المدرسة", "الطابعة", "لطباعة الكتب"),
    ("تحصد آلتان حقل قمح", "الآلة", "لحصاد الحقل"),
    ("تنظّف مكنستان آليتان قاعة رياضية", "المكنسة", "لتنظيف القاعة"),
)
# مدتا آلتين منفردتين (بالساعات) تنجزان العمل معًا في عدد صحيح من الساعات
WORK_PAIRS = tuple((a, b) for a in range(3, 41) for b in range(a + 1, 61) if (a * b) % (a + b) == 0)


def hours(n: int) -> str:
    """مدة بالساعات بصيغتها العربية."""
    return {1: "ساعة واحدة", 2: "ساعتين"}.get(n, f"${n}$ {'ساعات' if n <= 10 else 'ساعة'}")


def points(*pairs: tuple[Any, Any]) -> str:
    """أزواج مرتبة بترتيب ثابت، فالمجموعة نفسها تُكتب بالنص نفسه أيًّا كان ترتيب إدخالها."""
    ordered = sorted(set(pairs), key=lambda pair: (float(pair[0]), float(pair[1])))
    return " و".join(f"$({tex(px)},{tex(py)})$" for px, py in ordered)


def point_wrongs(
    answer: str, first: tuple[int, int], second: tuple[int, int]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """تبديل الإحداثيات وأخطاء الإشارة أولًا؛ البديلان الأخيران يخالفان الجواب وبعضهما دائمًا."""
    (x1, y1), (x2, y2) = first, second
    return tagged_wrongs(
        answer,
        ("swap", points((x1, y2), (x2, y1))),
        ("swap", points((y1, x1), (y2, x2))),
        ("sign", points((x1, -y1), (x2, -y2))),
        ("sign", points((-x1, y1), (-x2, y2))),
        ("nearby", points((x1 + 1, y1), (x2 + 1, y2))),
        ("nearby", points((x1, y1 + 1), (x2, y2 + 1))),
    )


# الدرس 2.7: حل المعادلات النسبية. المثالان 4 و5 إثرائيان: لا صيغة جوابها «لا حل»، ولا مسألة معدّل سرعة.
@variant("2.7", G10, example=1)
def rational_equation_with_constant_numerator(rng: random.Random) -> Problem:
    a, b = nz(rng, -9, 9), nz(rng, -9, 9)
    c = rng.choice([n for n in range(-6, 7) if n not in (0, 1)])
    value = sp.Rational(a, c) - b
    answer = solutions(value)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", solutions(sp.Rational(a, c) + b)),
        ("sign", solutions(-value)),
        ("formula", solutions(a * c - b)),
        ("formula", solutions(sp.Rational(c, a) - b)),
        ("nearby", solutions(value + 1)),
        ("nearby", solutions(value - 1)),
    )
    return Problem(
        "2.7",
        f"حلّ المعادلة النسبية ${frac(a, linear(-b))}={c}$.",
        answer,
        wrong,
        (
            f"نضرب طرفي المعادلة في المقام ${linear(-b)}$: ${a}={lead(c)}{shifted(-b)}$",
            f"${a}={lead(c)}x{c * b:+d}$",
            f"${lead(c)}x={a - c * b}$، إذن $x={tex(value)}$",
            f"القيمة لا تجعل المقام صفرًا، إذن حل المعادلة {answer}.",
        ),
        "K",
        {"type": "rational_equation", "lhs": a / (x + b), "rhs": sp.Integer(c), "solutions": (value,)},
        wrong_kinds=kinds,
    )


@variant("2.7", G10, example=1)
def rational_equation_as_proportion(rng: random.Random) -> Problem:
    a, c = rng.sample(range(1, 10), 2)
    b, d = rng.sample(range(-8, 9), 2)
    value = sp.Rational(c * b - a * d, a - c)
    answer = solutions(value)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", solutions(-value)),
        ("sign", solutions(sp.Rational(c * b + a * d, a - c))),
        ("formula", solutions(sp.Rational(c * b - a * d, a + c))),
        ("swap", solutions(sp.Rational(a * b - c * d, a - c))),
        ("nearby", solutions(value + 1)),
        ("nearby", solutions(value - 1)),
        ("nearby", solutions(value + 2)),
    )
    return Problem(
        "2.7",
        f"حلّ المعادلة النسبية ${frac(a, linear(-b))}={frac(c, linear(-d))}$.",
        answer,
        wrong,
        (
            f"نضرب طرفي المعادلة في المقام المشترك ${shifted(-b)}{shifted(-d)}$: "
            f"${lead(a)}{shifted(-d)}={lead(c)}{shifted(-b)}$",
            f"${lead(a)}x{signed(a * d)}={lead(c)}x{signed(c * b)}$",
            f"نجمع الحدود المتشابهة: ${lead(a - c)}x={c * b - a * d}$"
            + ("" if a - c == 1 else f"، إذن $x={tex(value)}$"),
            f"القيمة لا تجعل أيّ مقام صفرًا، إذن حل المعادلة {answer}.",
        ),
        "K",
        {"type": "rational_equation", "lhs": a / (x + b), "rhs": c / (x + d), "solutions": (value,)},
        wrong_kinds=kinds,
    )


def rational_sum_equation(a: int, p: int, q: int, c: int) -> tuple[str, sp.Expr, sp.Expr, sp.Expr]:
    """(نص المعادلة a/(x-p)+x/(x-q)=c/((x-p)(x-q)) بمقام مفكوك، طرفها الأيسر، طرفها الأيمن، المقام المفكوك)."""
    bottom = sp.expand((x - p) * (x - q))
    text = f"{frac(a, linear(p))}+{frac('x', linear(q))}={frac(c, bottom)}"
    return text, a / (x - p) + x / (x - q), c / bottom, bottom


@variant("2.7", G10, example=3)
def values_excluded_from_solutions(rng: random.Random) -> Problem:
    a, c = rng.randint(1, 5), nz(rng, -9, 9)
    p, q = rng.sample([n for n in range(-7, 8) if n], 2)
    text, lhs, rhs, bottom = rational_sum_equation(a, p, q, c)
    low, high = sorted((p, q))

    def both(first: int, second: int) -> str:
        return f"$x={first}$ و$x={second}$"

    answer = both(low, high)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", both(-high, -low)),
        ("partial", f"$x={low}$ فقط"),
        ("partial", f"$x={high}$ فقط"),
        ("formula", both(low + high, low * high)),
    )
    return Problem(
        "2.7",
        f"أيّ قيم $x$ لا يمكن أن تكون حلًّا للمعادلة ${text}$ لأنها تجعل مقامًا فيها يساوي صفرًا؟",
        answer,
        wrong,
        (
            f"المقام ${linear(p)}$ يساوي صفرًا عند $x={p}$، والمقام ${linear(q)}$ يساوي صفرًا عند $x={q}$.",
            f"${tex(bottom)}={product(low, high)}$، فيساوي صفرًا عند القيمتين نفسيهما.",
            f"إذن {answer} لا يمكن أن يكونا حلّين للمعادلة، وأي حل يساوي أحدهما حل غير مقبول.",
        ),
        "K",
        {"type": "excluded_values", "lhs": lhs, "rhs": rhs, "values": (p, q)},
        wrong_kinds=kinds,
    )


@variant("2.7", G10, example=2)
def work_rate_with_speed_ratio(rng: random.Random) -> Problem:
    together, noun, task = rng.choice(JOBS)
    k = rng.choice([2, 3, 4])
    t = k * rng.randint(1, 4)
    slow, fast = (k + 1) * t, (k + 1) * t // k
    first, second = f"{noun} الأولى", f"{noun} الثانية"
    wanted_fast = rng.random() < 0.5
    wanted = fast if wanted_fast else slow
    answer = hours(wanted)
    last = (
        f"سرعة {first} {RATIOS[k]} سرعة {second}، فتحتاج إلى ${frac(1, k)}$ من هذه المدة: "
        f"$\\dfrac{{{slow}}}{{{k}}}={fast}$، أي {answer}."
        if wanted_fast
        else f"إذن تحتاج {second} إلى {answer} {task} بمفردها."
    )
    wrong, kinds = tagged_wrongs(
        answer,
        ("concept", hours(slow if wanted_fast else fast)),
        ("formula", hours(k * t)),
        ("formula", hours(2 * t)),
        ("formula", hours(slow + fast)),
        ("nearby", hours(wanted + 1)),
        ("nearby", hours(wanted + 2)),
    )
    return Problem(
        "2.7",
        f"{together} في {hours(t)} عندما تعملان معًا. سرعة {first} في العمل تساوي {RATIOS[k]} سرعة "
        f"{second}. ما المدة التي تحتاج إليها {first if wanted_fast else second} {task} إذا عملت بمفردها؟",
        answer,
        wrong,
        (
            f"ليكن $x$ عدد الساعات التي تحتاج إليها {second} بمفردها، فمعدل عملها $\\dfrac{{1}}{{x}}$ من "
            f"العمل في الساعة، ومعدل عمل {first} $\\dfrac{{{k}}}{{x}}$.",
            f"معدل عملهما معًا $\\dfrac{{1}}{{{t}}}$: $\\dfrac{{1}}{{x}}+\\dfrac{{{k}}}{{x}}=\\dfrac{{1}}{{{t}}}$",
            f"نضرب الطرفين في ${t}x$: ${t}+{k * t}=x$، إذن $x={slow}$",
            last,
        ),
        "A",
        {"type": "work_rate", "times": (slow, fast), "together": t, "ratio": k, "answer": wanted},
        wrong_kinds=kinds,
    )


@variant("2.7", G10, example=2)
def work_rate_with_one_time_known(rng: random.Random) -> Problem:
    _, noun, task = rng.choice(JOBS)
    known, other = rng.sample(rng.choice(WORK_PAIRS), 2)
    t = known * other // (known + other)
    first, second = f"{noun} الأولى", f"{noun} الثانية"
    answer = hours(other)
    wrong, kinds = tagged_wrongs(
        answer,
        ("formula", hours(known - t)),
        ("formula", hours(known + t)),
        ("formula", hours(2 * t)),
        ("nearby", hours(other + 1)),
        ("nearby", hours(other + 2)),
        ("nearby", hours(other + 3)),
    )
    return Problem(
        "2.7",
        f"تحتاج {first} إلى {hours(known)} {task} إذا عملت بمفردها، وإذا عملت معها {second} أنجزتا "
        f"العمل في {hours(t)}. ما المدة التي تحتاج إليها {second} {task} إذا عملت بمفردها؟",
        answer,
        wrong,
        (
            f"ليكن $x$ عدد الساعات التي تحتاج إليها {second} بمفردها. معدل عمل {first} "
            f"$\\dfrac{{1}}{{{known}}}$ من العمل في الساعة، ومعدل عمل {second} $\\dfrac{{1}}{{x}}$.",
            f"معدل عملهما معًا $\\dfrac{{1}}{{{t}}}$: "
            f"$\\dfrac{{1}}{{{known}}}+\\dfrac{{1}}{{x}}=\\dfrac{{1}}{{{t}}}$",
            f"نضرب الطرفين في ${known * t}x$: ${t}x+{known * t}={known}x$",
            f"${lead(known - t)}x={known * t}$، إذن $x={other}$، فتحتاج {second} إلى {answer}.",
        ),
        "A",
        {"type": "work_rate", "times": (known, other), "together": t, "answer": other},
        wrong_kinds=kinds,
    )


@variant("2.7", G10, example=3)
def rational_equation_with_extraneous_solution(rng: random.Random) -> Problem:
    while True:
        a = rng.randint(1, 5)
        p, q = rng.sample([n for n in range(-6, 7) if n], 2)
        # بعد حذف المقامات: x²+(a-p)x-aq-c=0، وأحد جذريها p أو q يُعدِم مقامًا فهو غير مقبول.
        if rng.random() < 0.5:
            bad, good, c = p, -a, a * (p - q)
        else:
            bad, good, c = q, p - a - q, q * (q - p)
        if good not in (p, q) and (a, p, q) != (1, 5, 3):
            break
    text, lhs, rhs, _ = rational_sum_equation(a, p, q, c)
    cleared = sp.expand(a * (x - q) + x * (x - p) - c)
    answer = solutions(good)
    wrong, kinds = tagged_wrongs(
        answer,
        ("concept", solutions(bad)),
        ("concept", solutions(good, bad)),
        ("sign", solutions(-good)),
        ("sign", solutions(-good, -bad)),
        ("nearby", solutions(good + 1)),
        ("nearby", solutions(good - 1)),
    )
    return Problem(
        "2.7",
        f"ما حل المعادلة ${text}$؟",
        answer,
        wrong,
        (
            f"نضرب طرفي المعادلة في المقام المشترك الأصغر ${product(*sorted((p, q)))}$: "
            f"${lead(a)}{shifted(q)}+x{shifted(p)}={c}$",
            f"نبسّط ونكتب المعادلة في الصيغة القياسية: ${tex(cleared)}=0$",
            f"نحلّل إلى العوامل: ${product(*sorted((good, bad)))}=0$، إذن {solutions(good, bad)}",
            f"الحل $x={bad}$ غير مقبول لأنه يجعل مقامًا في المعادلة الأصلية يساوي صفرًا، إذن حل "
            f"المعادلة {answer}.",
        ),
        "A",
        {
            "type": "rational_equation",
            "lhs": lhs,
            "rhs": rhs,
            "solutions": (good,),
            "extraneous": (bad,),
            "cleared": cleared,
        },
        wrong_kinds=kinds,
    )


# «اكتشف الخطأ» في حل معادلة نسبية بصورة تناسب: الزلّة → (رقم الخطوة التي تقع فيها، نوع الخطأ من ERROR_KINDS).
PROPORTION_SLIPS = {
    "own_denominator": (1, "swap"),  # ضرب كل بسط في مقامه هو بدل مقام الطرف الآخر
    "partial_distribution": (2, "formula"),  # ضرب المعامل في الحد الأول من القوس وحده
    "moved_sign": (3, "sign"),  # نقل حد x إلى الطرف الأيسر دون تغيير إشارته
    "inverted": (4, "swap"),  # قسم معامل x على العدد بدل العكس
}


def proportion_chain(a: int, b: int, c: int, d: int, slip: str | None = None) -> Chain | None:
    """خطوات حل a/(x+b)=c/(x+d)، كل خطوة نصها ومعادلتها (عبارة = 0) من الأعداد نفسها.

    slip زلّة واحدة تُزرع في خطوتها وتُبنى عليها الخطوات التالية بلا خطأ آخر؛ None الحل الصحيح.
    يعيد None إن تعذّرت القسمة في الخطوة الأخيرة.
    """
    left, right = (b, d) if slip == "own_denominator" else (d, b)
    left_number, right_number = (left, right) if slip == "partial_distribution" else (a * left, c * right)
    coefficient = a + c if slip == "moved_sign" else a - c
    number = right_number - left_number
    if coefficient == 0 or (slip == "inverted" and number == 0):
        return None
    value = sp.Rational(coefficient, number) if slip == "inverted" else sp.Rational(number, coefficient)
    return [
        (
            f"نضرب طرفي المعادلة في المقام المشترك ${shifted(-b)}{shifted(-d)}$: "
            f"${lead(a)}{shifted(-left)}={lead(c)}{shifted(-right)}$",
            a * (x + left) - c * (x + right),
        ),
        (
            f"نفكّ القوسين: ${lead(a)}x{signed(left_number)}={lead(c)}x{signed(right_number)}$",
            a * x + left_number - c * x - right_number,
        ),
        (
            f"نجمع حدود $x$ في الطرف الأيسر والأعداد في الطرف الأيمن: ${lead(coefficient)}x={number}$",
            coefficient * x - number,
        ),
        (f"نقسم الطرفين على ${coefficient}$: $x={exact(value)}$", x - value),
    ]


@variant("2.7", G10, example=1, registry=ERROR_SPOTTING)
def spot_error_in_rational_proportion(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(PROPORTION_SLIPS))
    while True:
        a, c = rng.sample(range(2, 10), 2)
        b, d = rng.sample([n for n in range(-8, 9) if n], 2)
        shown, solved = proportion_chain(a, b, c, d, slip), proportion_chain(a, b, c, d)
        # معامل x بعد الجمع لا يساوي ±1 فالقسمة خطوة فعلية، والزلّة تغيّر الحل
        if abs(a - c) >= 2 and shown is not None and solved is not None and shown[-1][1] != solved[-1][1]:
            break
    lhs, rhs = a / (x + b), c / (x + d)
    value = sp.Rational(c * b - a * d, a - c)
    return spotted_chain(
        "2.7",
        f"حلّ طالب المعادلة النسبية ${frac(a, linear(-b))}={frac(c, linear(-d))}$ {SPOT_TASK}",
        (shown, solved),
        PROPORTION_SLIPS[slip],
        solutions(value),
        sp.numer(sp.together(lhs - rhs)),
        (value,),
    )


# الدرس 2.8: الأنظمة الخطية-التربيعية
SYSTEM_COUNTS = {0: "ليس للنظام حل", 1: "للنظام حل واحد", 2: "للنظام حلّان"}
CROSSINGS = {0: "لا يتقاطعان", 1: "يتقاطعان في نقطة واحدة", 2: "يتقاطعان في نقطتين"}


def line_value(m_: int, d: int, at: int) -> str:
    """تعويض قيمة x في المعادلة الخطية y=mx+d."""
    return f"$y={lead(m_)}({at}){signed(d)}={m_ * at + d}$"


def meters(n: int) -> str:
    return f"${n}$ {'أمتار' if n <= 10 else 'مترًا'}"


@variant("2.8", G10, example=1)
def number_of_solutions_of_linear_quadratic_system(rng: random.Random) -> Problem:
    count, h = rng.choice([0, 1, 2]), rng.randint(-4, 4)
    slope, d = nz(rng, -3, 3), rng.randint(-6, 6)
    gap = {0: 1, 1: 0, 2: -1}[count] * rng.randint(1, 9)
    line = slope * x + d
    difference = sp.expand((x - h) ** 2 + gap)
    parabola = sp.expand(difference + line)
    b, c = -2 * h, h * h + gap
    answer = SYSTEM_COUNTS[count]
    wrong, kinds = tagged_wrongs(
        answer,
        *[("concept", text) for n, text in SYSTEM_COUNTS.items() if n != count],
        ("concept", "للنظام عدد لا نهائي من الحلول"),
    )
    return Problem(
        "2.8",
        f"ما عدد حلول النظام الخطي-التربيعي $y={tex(parabola)}$ و$y={tex(line)}$؟",
        answer,
        wrong,
        (
            f"نساوي المقدارين: ${tex(parabola)}={tex(line)}$، أي ${tex(difference)}=0$",
            *formula_values(1, b, c, b * b - 4 * c),
            f"المميز {('سالب', 'يساوي صفرًا', 'موجب')[count]}، فالمستقيم والقطع المكافئ "
            f"{CROSSINGS[count]}، إذن {answer}.",
        ),
        "K",
        {"type": "system", "equations": (y - parabola, y - line), "count": count},
        wrong_kinds=kinds,
    )


def crossing_system(
    rng: random.Random, leading: int
) -> tuple[sp.Expr, sp.Expr, sp.Expr, int, int, tuple[int, int], tuple[int, int]]:
    """(القطع المكافئ، المستقيم، الفرق بينهما، الميل، المقطع، نقطتا التقاطع) بإحداثيات صحيحة."""
    r1, r2 = two_roots(rng, -5, 5)
    slope, d = nz(rng, -4, 4), rng.randint(-6, 6)
    line = slope * x + d
    difference = sp.expand(leading * (x - r1) * (x - r2))
    return (
        sp.expand(difference + line),
        line,
        difference,
        slope,
        d,
        (r1, slope * r1 + d),
        (r2, slope * r2 + d),
    )


def back_substitution(slope: int, d: int, r1: int, r2: int) -> str:
    return (
        f"نعوّض في المعادلة الخطية: عند $x={r1}$: {line_value(slope, d, r1)}، وعند $x={r2}$: "
        f"{line_value(slope, d, r2)}"
    )


@variant("2.8", G10, example=2)
def system_solutions_from_intersection_points(rng: random.Random) -> Problem:
    parabola, line, _, slope, d, first, second = crossing_system(rng, rng.choice([1, -1]))
    answer = points(first, second)
    wrong, kinds = point_wrongs(answer, first, second)
    return Problem(
        "2.8",
        f"يتقاطع التمثيلان البيانيان للمعادلتين $y={tex(parabola)}$ و$y={tex(line)}$ في نقطتين "
        f"إحداثياهما $x$ هما ${first[0]}$ و${second[0]}$. ما حلول النظام المكوّن من المعادلتين؟",
        answer,
        wrong,
        (
            "حلول النظام الخطي-التربيعي هي نقاط تقاطع المستقيم مع القطع المكافئ.",
            back_substitution(slope, d, first[0], second[0]),
            f"إذن حلّا النظام {answer}.",
        ),
        "K",
        {"type": "system", "equations": (y - parabola, y - line), "solutions": (first, second)},
        wrong_kinds=kinds,
    )


@variant("2.8", G10, example=3)
def solve_system_by_elimination(rng: random.Random) -> Problem:
    parabola, line, difference, slope, d, first, second = crossing_system(rng, 1)
    answer = points(first, second)
    wrong, kinds = point_wrongs(answer, first, second)
    return Problem(
        "2.8",
        f"حلّ النظام الخطي-التربيعي $y={tex(parabola)}$ و$y={tex(line)}$ بطريقة الحذف.",
        answer,
        wrong,
        (
            f"نطرح المعادلة الخطية من المعادلة التربيعية لحذف $y$: $0={tex(difference)}$",
            f"نحلّل إلى العوامل: ${product(first[0], second[0])}=0$، إذن {solutions(first[0], second[0])}",
            back_substitution(slope, d, first[0], second[0]),
            f"إذن حلّا النظام {answer}.",
        ),
        "A",
        {"type": "system", "equations": (y - parabola, y - line), "solutions": (first, second)},
        wrong_kinds=kinds,
    )


@variant("2.8", G10, example=4)
def solve_system_by_substitution(rng: random.Random) -> Problem:
    leading = rng.choice([-3, -2, -1, 2, 3])
    parabola, line, difference, slope, d, first, second = crossing_system(rng, leading)
    monic = sp.expand(difference / leading)
    answer = points(first, second)
    wrong, kinds = point_wrongs(answer, first, second)
    return Problem(
        "2.8",
        f"حلّ النظام الخطي-التربيعي $y={tex(line)}$ و$y={tex(parabola)}$ بطريقة التعويض.",
        answer,
        wrong,
        (
            f"نعوّض ${tex(line)}$ بدل $y$ في المعادلة التربيعية: ${tex(line)}={tex(parabola)}$",
            f"نكتب المعادلة في الصيغة القياسية: ${tex(difference)}=0$، ونقسم طرفيها على ${leading}$: "
            f"${tex(monic)}=0$",
            f"نحلّل إلى العوامل: ${product(first[0], second[0])}=0$، إذن {solutions(first[0], second[0])}",
            back_substitution(slope, d, first[0], second[0]),
            f"إذن حلّا النظام {answer}.",
        ),
        "A",
        {"type": "system", "equations": (y - parabola, y - line), "solutions": (first, second)},
        wrong_kinds=kinds,
    )


@variant("2.8", G10, example=4)
def ball_and_drone_at_same_height(rng: random.Random) -> Problem:
    at, n = rng.randint(3, 7), rng.randint(1, 9)
    slope, d = rng.randint(1, 4), rng.randint(1, 10)
    drone = slope * x + d
    # -5x²+(slope+5·at-n)x+d+n·at ناقص المستقيم = -(x-at)(5x+n): الجذر الموجب الوحيد هو at.
    ball = -5 * x**2 + (slope + 5 * at - n) * x + d + n * at
    height, other = slope * at + d, sp.Rational(-n, 5)

    def text(time: int, level: int) -> str:
        return f"بعد ${time}$ ثوانٍ، وعلى ارتفاع {meters(level)}"

    answer = text(at, height)
    wrong, kinds = tagged_wrongs(
        answer,
        ("coefficient", text(at, d + n * at)),
        *[("nearby", text(at + step, slope * (at + step) + d)) for step in (1, 2, 3)],
    )
    return Problem(
        "2.8",
        "قُذفت كرة إلى الأعلى من سطح مبنى، ويُعطى ارتفاعها بالأمتار بعد $x$ من الثواني بالدالة "
        f"$y={tex(ball)}$. في اللحظة نفسها بدأت طائرة مسيّرة بالصعود، ويُعطى ارتفاعها بالدالة "
        f"$y={tex(drone)}$. بعد كم ثانية يكون للكرة والطائرة الارتفاع نفسه؟ وما ذلك الارتفاع؟",
        answer,
        wrong,
        (
            f"يكون الارتفاعان متساويين عندما ${tex(ball)}={tex(drone)}$",
            f"نكتب المعادلة في الصيغة القياسية: ${tex(sp.expand(drone - ball))}=0$",
            f"نحلّل إلى العوامل: ${shifted(at)}(5x+{n})=0$، إذن $x={at}$ أو $x={tex(other)}$",
            f"الزمن لا يكون سالبًا، إذن $x={at}$، والارتفاع بالأمتار عندها {line_value(slope, d, at)}",
        ),
        "A",
        {
            "type": "system",
            "equations": (y - ball, y - drone),
            "solutions": ((at, height), (other, slope * other + d)),
        },
        wrong_kinds=kinds,
    )


# «اكتشف الخطأ» في حل نظام خطي-تربيعي بالحذف: الزلّة → (رقم الخطوة التي تقع فيها، نوع الخطأ من ERROR_KINDS).
ELIMINATION_SLIPS = {
    "linear_sign": (1, "sign"),  # طرح حد x من المعادلة الخطية دون تغيير إشارته
    "root_sign": (2, "sign"),  # قرأ الحلّين من العاملين بإشارتيهما
    "no_intercept": (3, "formula"),  # عوّض في المعادلة الخطية وأسقط حدها الثابت
    "swapped": (4, "swap"),  # كتب الزوج المرتب (y, x)
}


def elimination_item(r1: int, r2: int, slope: int, d: int, slip: str) -> ErrorSpotting | None:
    """النظام y=x²+bx+c وy=slope·x+d المتقاطعان عند x=r₁ وx=r₂: الفرق، ثم حلّاه، ثم قيمتا y، ثم النقطتان."""
    step, kind = ELIMINATION_SLIPS[slip]
    b, c = slope - (r1 + r2), r1 * r2 + d
    line, parabola = slope * x + d, x**2 + b * x + c
    if slip == "linear_sign":  # الفرق بعد الزلّة يبقى قابلًا للتحليل بحلّين صحيحين مختلفين
        disc = (b + slope) ** 2 - 4 * (c - d)
        if disc <= 0 or math.isqrt(disc) ** 2 != disc:
            return None
    middle, constant, low, high = ref(1, 0), ref(1, 1), ref(2, 0), ref(2, 1)
    spread = sp.sqrt(middle**2 - 4 * constant)
    rules: tuple[Rule, ...] = (
        (b - slope, c - d),
        ((-middle - spread) / 2, (-middle + spread) / 2),
        (slope * low + d, slope * high + d),
        (low, ref(3, 0), high, ref(3, 1)),
    )
    wrong: Rule = {
        "linear_sign": (b + slope, c - d),
        "root_sign": ((middle - spread) / 2, (middle + spread) / 2),
        "no_intercept": (slope * low, slope * high),
        "swapped": (ref(3, 0), low, ref(3, 1), high),
    }[slip]

    def texts(rows: list[Row], slipped: bool) -> tuple[str, ...]:
        (p, q), (first, second), (y1, y2), (a1, b1, a2, b2) = (tuple(int(v) for v in row) for row in rows)
        gap = math.isqrt(p * p - 4 * q)

        def value(at: int, found: int) -> str:
            tail = "" if slipped and slip == "no_intercept" else signed(d)
            return f"عند $x={at}$: $y={lead(slope)}({at}){tail}={found}$"

        return (
            f"نطرح المعادلة الخطية من المعادلة التربيعية لحذف $y$: $0={tex(x**2 + p * x + q)}$",
            f"نحلّل إلى العوامل: ${product((-p - gap) // 2, (-p + gap) // 2)}=0$، إذن "
            f"{solutions(first, second)}",
            f"نعوّض في المعادلة الخطية: {value(first, y1)}، و{value(second, y2)}",
            f"إذن حلّا النظام {points((a1, b1), (a2, b2))}",
        )

    return spotted_values(
        "2.8",
        f"حلّ طالب النظام الخطي-التربيعي $y={tex(parabola)}$ و$y={tex(line)}$ بطريقة الحذف {SPOT_TASK}",
        rules,
        (step, kind, wrong),
        texts,
        points((r1, slope * r1 + d), (r2, slope * r2 + d)),
        {"quantity": "system_points", "equations": (y - parabola, y - line)},
    )


@variant("2.8", G10, example=3, registry=ERROR_SPOTTING)
def spot_error_in_solving_system_by_elimination(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(ELIMINATION_SLIPS))
    while True:
        r1, r2 = two_roots(rng, -6, 6)
        item = elimination_item(r1, r2, nz(rng, -4, 4), nz(rng, -6, 6), slip)
        if item is not None:
            return item


# الدرس 2.9: المتباينات التربيعية. المثال 4 (النمذجة بمتباينة) إثرائي: لا مسألة سياقية هنا.
OP_TEX = {"<": "<", ">": ">", "<=": "\\le", ">=": "\\ge"}
OP_NAMES = {"<": "أصغر من", ">": "أكبر من", "<=": "أصغر من أو يساوي", ">=": "أكبر من أو يساوي"}
LESS, MORE = {True: "\\le", False: "<"}, {True: "\\ge", False: ">"}
MINUS_INFINITY, INFINITY = "-\\infty", "\\infty"
REALS, EMPTY = "مجموعة الأعداد الحقيقية $\\mathbb{R}$", "المجموعة الخالية $\\emptyset$"
# قطعة من مجموعة الحل: (الطرف الأصغر أو None لسالب اللانهاية، الطرف الأكبر أو None، مغلقة يسارًا، مغلقة يمينًا)
Piece = tuple[Any, Any, bool, bool]


def interval(low: Any, high: Any, closed_low: bool = False, closed_high: bool = False) -> str:
    """فترة برموز الكتاب: القوس المغلق نحو الداخل والمفتوح نحو الخارج، وطرف اللانهاية مفتوح دائمًا."""
    left = "[" if closed_low and low is not None else "]"
    right = "]" if closed_high and high is not None else "["
    start = MINUS_INFINITY if low is None else tex(low)
    end = INFINITY if high is None else tex(high)
    return f"{left}{start},{end}{right}"


def inequality_solution(r1: int, r2: int, inside: bool, strict: bool) -> tuple[str, str, tuple[Piece, ...]]:
    """(الحل بصيغة المتباينة، الحل بالفترات، قطع مجموعة الحل) بين الجذرين أو خارجهما."""
    closed = not strict
    if inside:
        return (
            f"${r1}{LESS[closed]} x{LESS[closed]} {r2}$",
            f"الفترة ${interval(r1, r2, closed, closed)}$",
            ((r1, r2, closed, closed),),
        )
    return (
        f"$x{LESS[closed]} {r1}$ أو $x{MORE[closed]} {r2}$",
        f"الفترة ${interval(None, r1, False, closed)}$ أو الفترة ${interval(r2, None, closed, False)}$",
        ((None, r1, False, closed), (r2, None, closed, False)),
    )


# أنواع أخطاء البدائل الثلاثة في solved_inequality بترتيبها: الجانب معكوس، الطرف المفتوح/المغلق معكوس، كلاهما
OTHERS_KINDS = ("direction", "partial", "concept")


def solved_inequality(
    leading: int, r1: int, r2: int, op: str
) -> tuple[str, str, tuple[Piece, ...], tuple[str, ...]]:
    """(الحل، الحل بالفترات، القطع، البدائل الثلاثة) للمتباينة leading(x-r₁)(x-r₂) op 0."""
    inside, strict = (leading > 0) != (op in (">", ">=")), op in ("<", ">")
    answer, intervals, pieces = inequality_solution(r1, r2, inside, strict)
    others = tuple(
        inequality_solution(r1, r2, *flags)[0]
        for flags in ((not inside, strict), (inside, not strict), (not inside, not strict))
    )
    return answer, intervals, pieces, others


@variant("2.9", G10, example=1)
def quadratic_inequality_from_x_intercepts(rng: random.Random) -> Problem:
    r1, r2 = two_roots(rng, -7, 7)
    leading, op = rng.choice([-2, -1, 1, 2]), rng.choice(list(OP_TEX))
    f = sp.expand(leading * (x - r1) * (x - r2))
    answer, intervals, pieces, others = solved_inequality(leading, r1, r2, op)
    above = op in (">", ">=")
    where = (
        f"الواقعة بين ${r1}$ و${r2}$" if (leading > 0) != above else f"الأصغر من ${r1}$ أو الأكبر من ${r2}$"
    )
    ends = "لا ينتميان" if op in ("<", ">") else "ينتميان"
    return Problem(
        "2.9",
        f"يقطع التمثيل البياني للدالة $f(x)={tex(f)}$ المحور $x$ عند $x={r1}$ و$x={r2}$، ويفتح القطع "
        f"المكافئ إلى {opening(leading)}. ما حل المتباينة ${tex(f)}{OP_TEX[op]} 0$؟",
        answer,
        others,
        (
            f"المتباينة تحوي الرمز «{OP_NAMES[op]}»، فنحدّد الجزء من المنحنى الذي يقع "
            f"{'فوق' if above else 'تحت'} المحور $x$.",
            f"القطع المكافئ يفتح إلى {opening(leading)}، فهذا الجزء يقابل قيم $x$ {where}، والعددان "
            f"${r1}$ و${r2}$ {ends} إلى مجموعة الحلول.",
            f"إذن حل المتباينة {answer}، أي {intervals}.",
        ),
        "K",
        {"type": "inequality", "conditions": ((f, op),), "pieces": pieces},
        wrong_kinds=OTHERS_KINDS,
    )


@variant("2.9", G10, example=2)
def quadratic_inequality_without_zeros(rng: random.Random) -> Problem:
    leading, h, size = rng.choice([-2, -1, 1, 2]), rng.randint(-4, 4), rng.randint(1, 6)
    k, op = (size if leading > 0 else -size), rng.choice(list(OP_TEX))
    f = sp.expand(leading * (x - h) ** 2 + k)
    holds = (leading > 0) == (op in (">", ">="))
    answer = REALS if holds else EMPTY
    side = "فوق" if leading > 0 else "تحت"
    return Problem(
        "2.9",
        f"رأس القطع المكافئ الذي يمثّل الدالة $f(x)={tex(f)}$ هو النقطة $({h},{k})$، ويفتح القطع إلى "
        f"{opening(leading)}. ما حل المتباينة ${tex(f)}{OP_TEX[op]} 0$؟",
        answer,
        (EMPTY if holds else REALS, f"$x>{h}$", f"$x<{h}$"),
        (
            f"الرأس يقع {side} المحور $x$ والقطع المكافئ يفتح إلى {opening(leading)}، فلا يقطع التمثيل "
            f"البياني المحور $x$ ويقع المنحنى كله {side} المحور $x$.",
            f"إذن قيم الدالة {'موجبة' if leading > 0 else 'سالبة'} عند كل قيم $x$، "
            f"{'فكل عدد حقيقي يحقق المتباينة' if holds else 'فلا يحقق المتباينة أي عدد حقيقي'}.",
            f"حل المتباينة {answer}.",
        ),
        "K",
        {
            "type": "inequality",
            "conditions": ((f, op),),
            "pieces": ((None, None, False, False),) if holds else (),
        },
        wrong_kinds=("concept", "concept", "concept"),
    )


def belongs(closed: bool) -> str:
    return "ينتمي إلى المجموعة فالقوس عنده مغلق" if closed else "لا ينتمي إلى المجموعة فالقوس عنده مفتوح"


@variant("2.9", G10, example=1)
def interval_for_set_of_real_numbers(rng: random.Random) -> Problem:
    conditions: tuple[tuple[sp.Expr, str], ...]
    pieces: tuple[Piece, ...]
    if rng.random() < 0.5:
        low, high = two_roots(rng, -9, 9)
        closed_low, closed_high = rng.random() < 0.5, rng.random() < 0.5
        condition = f"{low}{LESS[closed_low]} x{LESS[closed_high]} {high}"
        answer = f"${interval(low, high, closed_low, closed_high)}$"
        wrong = tuple(
            f"${interval(low, high, *flags)}$"
            for flags in (
                (not closed_low, closed_high),
                (closed_low, not closed_high),
                (not closed_low, not closed_high),
            )
        )
        kinds = ("partial", "partial", "concept")
        conditions = ((x - low, ">=" if closed_low else ">"), (x - high, "<=" if closed_high else "<"))
        pieces = ((low, high, closed_low, closed_high),)
        steps = (
            f"المجموعة تضم الأعداد الحقيقية الواقعة بين ${low}$ و${high}$، فطرفا الفترة ${low}$ و${high}$.",
            f"العدد ${low}$ {belongs(closed_low)}، والعدد ${high}$ {belongs(closed_high)}.",
        )
    else:
        at, closed, upward = rng.randint(-9, 9), rng.random() < 0.5, rng.random() < 0.5

        def ray(up: bool, shut: bool) -> str:
            return f"${interval(at, None, shut, False) if up else interval(None, at, False, shut)}$"

        condition = f"x{(MORE if upward else LESS)[closed]} {at}"
        answer = ray(upward, closed)
        wrong = (ray(upward, not closed), ray(not upward, closed), ray(not upward, not closed))
        kinds = ("partial", "direction", "concept")
        conditions = ((x - at, (">" if upward else "<") + ("=" if closed else "")),)
        pieces = ((at, None, closed, False),) if upward else ((None, at, False, closed),)
        steps = (
            f"المجموعة تضم الأعداد الحقيقية {'الأكبر من' if upward else 'الأصغر من'}"
            f"{' أو تساوي' if closed else ''} ${at}$، فهي غير محدودة من جهة "
            f"{RIGHT if upward else LEFT}، ويُكتب عندها الرمز ${INFINITY if upward else MINUS_INFINITY}$ "
            "بقوس مفتوح.",
            f"العدد ${at}$ {belongs(closed)}.",
        )
    return Problem(
        "2.9",
        f"اكتب الفترة التي تمثّل مجموعة الأعداد الحقيقية $x$ التي تحقق ${condition}$.",
        answer,
        wrong,
        (*steps, f"إذن الفترة هي {answer}."),
        "K",
        {"type": "inequality", "conditions": conditions, "pieces": pieces},
        wrong_kinds=kinds,
    )


def algebraic_inequality(f: sp.Expr, leading: int, r1: int, r2: int, op: str, factored: str) -> Problem:
    """حل جبري لمتباينة تربيعية جذراها r₁<r₂: المعادلة المرتبطة ثم اختبار قيمة من كل فترة."""
    answer, intervals, pieces, others = solved_inequality(leading, r1, r2, op)
    middle = r1 + 1 if r2 - r1 >= 2 else sp.Rational(r1 + r2, 2)
    tests = "، و".join(
        f"عند $x={tex(at)}$ قيمة المقدار ${tex(f.subs(x, at))}$" for at in (r1 - 1, middle, r2 + 1)
    )
    wanted = ("موجبًا" if op in (">", ">=") else "سالبًا") + ("" if op in ("<", ">") else " أو صفرًا")
    return Problem(
        "2.9",
        f"حلّ المتباينة التربيعية ${tex(f)}{OP_TEX[op]} 0$ جبريًّا.",
        answer,
        others,
        (
            f"نحل المعادلة المرتبطة بالمتباينة ${tex(f)}=0$: ${factored}=0$، إذن {solutions(r1, r2)}",
            f"نختبر قيمة من كل فترة يحددها الحلّان على خط الأعداد: {tests}.",
            f"تتحقق المتباينة عندما يكون المقدار {wanted}، إذن الحل {answer}.",
            f"باستعمال الفترات: {intervals}.",
        ),
        "A",
        {"type": "inequality", "conditions": ((f, op),), "pieces": pieces},
        wrong_kinds=OTHERS_KINDS,
    )


@variant("2.9", G10, example=3)
def solve_quadratic_inequality_by_factoring(rng: random.Random) -> Problem:
    r1, r2 = two_roots(rng, -7, 7)
    f = sp.expand((x - r1) * (x - r2))
    return algebraic_inequality(f, 1, r1, r2, rng.choice(list(OP_TEX)), product(r1, r2))


@variant("2.9", G10, example=3)
def solve_quadratic_inequality_with_common_factor(rng: random.Random) -> Problem:
    leading, r = rng.choice([-3, -2, -1, 2, 3]), nz(rng, -6, 6)
    f = sp.expand(leading * x * (x - r))
    low, high = sorted((0, r))
    return algebraic_inequality(
        f, leading, low, high, rng.choice(list(OP_TEX)), f"{lead(leading)}x{shifted(r)}"
    )


# «اكتشف الخطأ» في حل متباينة تربيعية جبريًّا: الزلّة → (رقم الخطوة التي تقع فيها، نوع الخطأ من ERROR_KINDS).
INEQUALITY_SLIPS = {
    "root_sign": (1, "sign"),  # قرأ الحلّين من العاملين بإشارتيهما
    "product_sign": (2, "sign"),  # أخطأ إشارة حاصل ضرب العاملين عند قيمة الاختبار
    "reversed_region": (3, "direction"),  # عكس الحكم: جعل الحل خارج الحلّين بدل بينهما أو العكس
    "endpoint": (4, "partial"),  # ضمّ الحلّين إلى مجموعة الحل أو استبعدهما خلافًا لرمز المتباينة
}


def inequality_item(r1: int, r2: int, op: str, slip: str) -> ErrorSpotting | None:
    """المتباينة (x-r₁)(x-r₂) op 0 ومنتصف r₁ وr₂ صحيح: الحلّان، ثم قيمة المقدار بينهما، ثم الحكم، ثم الحل.

    الصف الأخير (الطرف الأصغر، الأكبر، 1 إن كان الحل بينهما، 1 إن انتمى الطرفان).
    """
    step, kind = INEQUALITY_SLIPS[slip]
    above, closed = op in (">", ">="), int(op in ("<=", ">="))
    low, high = ref(1, 0), ref(1, 1)
    at = (low + high) / 2
    tested = (at - r1) * (at - r2)
    satisfied = (1 + (1 if above else -1) * sp.sign(ref(2))) / 2
    rules: tuple[Rule, ...] = ((r1, r2), (tested,), (satisfied,), (low, high, ref(3), closed))
    wrong: Rule = {
        "root_sign": (-r2, -r1),
        "product_sign": (-tested,),
        "reversed_region": (1 - satisfied,),
        "endpoint": (low, high, ref(3), 1 - closed),
    }[slip]
    f = sp.expand((x - r1) * (x - r2))
    wanted = ("موجبًا" if above else "سالبًا") + (" أو صفرًا" if closed else "")

    def texts(rows: list[Row], slipped: bool) -> tuple[str, ...]:
        (first, second), (found,), (inside,), (*_, shut) = (tuple(int(v) for v in row) for row in rows)
        test = (first + second) // 2
        return (
            f"نحل المعادلة المرتبطة بالمتباينة ${tex(f)}=0$ بالتحليل إلى العوامل: ${product(r1, r2)}=0$، "
            f"إذن {solutions(first, second)}",
            f"نختبر قيمة بين الحلّين: عند $x={test}$ قيمة المقدار "
            f"$({minus(test, r1)})({minus(test, r2)})={found}$",
            f"القيمة {'موجبة' if found > 0 else 'سالبة'} والمتباينة تطلب أن يكون المقدار {wanted}، فالأعداد "
            f"الواقعة بين الحلّين {'تحقق' if inside else 'لا تحقق'} المتباينة",
            f"رمز المتباينة «{OP_NAMES[op]}»، إذن الحل "
            f"{inequality_solution(first, second, bool(inside), not shut)[0]}",
        )

    item = spotted_values(
        "2.9",
        f"حلّ طالب المتباينة التربيعية ${tex(f)}{OP_TEX[op]} 0$ جبريًّا {SPOT_TASK}",
        rules,
        (step, kind, wrong),
        texts,
        solved_inequality(1, r1, r2, op)[0],
        {"quantity": "inequality_solution", "f": f, "op": op},
    )
    # قيمة الاختبار المعروضة لا تكون صفرًا (منتصف الحلّين المعكوسين قد يقع على جذر)
    return None if item is None or item.check["steps"][1][0] == 0 else item


@variant("2.9", G10, example=3, registry=ERROR_SPOTTING)
def spot_error_in_solving_quadratic_inequality(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(INEQUALITY_SLIPS))
    while True:
        r1 = rng.randint(-7, 5)
        item = inequality_item(r1, r1 + rng.choice([2, 4, 6]), rng.choice(list(OP_TEX)), slip)
        if item is not None:
            return item


# الدرس 2.10: معادلة الدائرة. المثال 4 (إكمال المربع لإيجاد المركز ونصف القطر) إثرائي: المعادلات هنا في
# الصيغة القياسية (x-h)²+(y-k)²=r² دائمًا.
ROUND_PLACES = (
    ("نافورة دائرية", "حافة النافورة"),
    ("حوض زهور دائري", "حافة الحوض"),
    ("ساحة دائرية", "حافة الساحة"),
    ("مضمار جري دائري", "المضمار"),
)
POSITIONS = {"on": "تقع على الدائرة", "inside": "تقع داخل الدائرة", "outside": "تقع خارج الدائرة"}
RELATIONS = {"on": ("=", "يساوي"), "inside": ("<", "أصغر من"), "outside": (">", "أكبر من")}


def lattice(r2: int) -> list[tuple[int, int]]:
    """النقاط ذات الإحداثيات الصحيحة على الدائرة x²+y²=r2."""
    reach = math.isqrt(r2)
    return [
        (px, py)
        for px in range(-reach, reach + 1)
        for py in range(-reach, reach + 1)
        if px * px + py * py == r2
    ]


# مربعات أنصاف أقطار تمرّ دوائرها بنقاط إحداثياتها صحيحة غير صفرية (إزاحات عن المركز)
SLANTED = {r2: [p for p in lattice(r2) if p[0] and p[1]] for r2 in range(5, 101)}
CIRCLE_SQUARES = tuple(r2 for r2, found in SLANTED.items() if found)


def line_circle_systems() -> list[tuple[int, int, int, tuple[int, int], tuple[int, int]]]:
    """(r²، الميل، المقطع، نقطتا التقاطع) لمستقيم y=mx+c بمعاملات صحيحة يقطع x²+y²=r² في نقطتين صحيحتين."""
    found = []
    for r2 in range(5, 101):
        on = lattice(r2)
        for x1, y1 in on:
            for x2, y2 in on:
                if x1 < x2 and (y2 - y1) % (x2 - x1) == 0:
                    slope = (y2 - y1) // (x2 - x1)
                    c = y1 - slope * x1
                    if slope and abs(slope) <= 3 and abs(c) <= 12:
                        found.append((r2, slope, c, (x1, y1), (x2, y2)))
    return found


LINE_CIRCLE_SYSTEMS = line_circle_systems()


def squared(name: str, center: int) -> str:
    return f"{name}^2" if center == 0 else f"({name}{-center:+d})^2"


def circle(h: int, k: int, r2: Any) -> str:
    """معادلة الدائرة في الصيغة القياسية نصًّا."""
    return f"${squared('x', h)}+{squared('y', k)}={tex(r2)}$"


def circle_check(h: int, k: int, r2: int, **extra: Any) -> dict[str, Any]:
    equation = sp.expand((x - h) ** 2 + (y - k) ** 2 - r2)
    return {"type": "circle", "equation": equation, "center": (h, k), "radius2": r2, **extra}


def radius(rng: random.Random) -> tuple[str, int, int]:
    """(طول نصف القطر نصًّا، مربعه، الخطأ الشائع: نصف القطر بلا تربيع أو المجذور مربّعًا)."""
    if rng.random() < 0.3:
        n = rng.choice(SQUARE_FREE)
        return f"\\sqrt{{{n}}}", n, n * n
    r = rng.randint(2, 9)
    return str(r), r * r, r


@variant("2.10", G10, example=2)
def circle_equation_from_center_and_radius(rng: random.Random) -> Problem:
    h, k = rng.randint(-7, 7), rng.randint(-7, 7)
    shown, r2, slip = radius(rng)
    answer = circle(h, k, r2)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", circle(-h, -k, r2)),
        ("square", circle(h, k, slip)),
        ("sign", circle(-h, -k, slip)),
        ("swap", circle(k, h, r2)),
        ("formula", circle(h, k, 2 * r2)),
        ("nearby", circle(h, k, r2 + 1)),
        ("formula", circle(h, k, 3 * r2)),
    )
    return Problem(
        "2.10",
        f"اكتب معادلة الدائرة التي مركزها $({h},{k})$ وطول نصف قطرها ${shown}$.",
        answer,
        wrong,
        (
            f"$h={h}$، $k={k}$، $r={shown}$",
            "الصيغة القياسية لمعادلة الدائرة: $(x-h)^2+(y-k)^2=r^2$",
            f"نعوّض ونبسّط: $r^2={r2}$، إذن معادلة الدائرة {answer}.",
        ),
        "K",
        circle_check(h, k, r2),
        wrong_kinds=kinds,
    )


@variant("2.10", G10, example=2)
def center_and_radius_from_circle_equation(rng: random.Random) -> Problem:
    h, k = rng.randint(-7, 7), nz(rng, -7, 7)
    shown, r2, _ = radius(rng)

    def text(a: int, b: int, length: str) -> str:
        return f"المركز $({a},{b})$، وطول نصف القطر ${length}$"

    answer = text(h, k, shown)
    wrong, kinds = tagged_wrongs(
        answer,
        ("sign", text(-h, -k, shown)),
        ("square", text(h, k, str(r2))),
        ("sign", text(-h, -k, str(r2))),
        ("swap", text(k, h, shown)),
    )
    return Problem(
        "2.10",
        f"أوجد مركز الدائرة {circle(h, k, r2)} وطول نصف قطرها.",
        answer,
        wrong,
        (
            "الصيغة القياسية لمعادلة الدائرة: $(x-h)^2+(y-k)^2=r^2$",
            f"نكتب المعادلة بهذه الصيغة: $(x-({h}))^2+(y-({k}))^2=({shown})^2$",
            f"إذن $h={h}$، $k={k}$، $r={shown}$: {answer}.",
        ),
        "K",
        circle_check(h, k, r2),
        wrong_kinds=kinds,
    )


@variant("2.10", G10, example=1)
def circle_equation_from_center_and_point(rng: random.Random) -> Problem:
    h, k = rng.randint(-6, 6), rng.randint(-6, 6)
    dx, dy = nz(rng, -6, 6), nz(rng, -6, 6)
    p, q, r2 = h + dx, k + dy, dx * dx + dy * dy
    answer = circle(h, k, r2)
    wrong, kinds = tagged_wrongs(
        answer,
        ("concept", circle(p, q, r2)),
        ("sign", circle(-h, -k, r2)),
        ("formula", circle(h, k, abs(dx) + abs(dy))),
        ("formula", circle(h, k, 2 * r2)),
        ("nearby", circle(h, k, r2 + 1)),
    )
    return Problem(
        "2.10",
        f"اكتب معادلة الدائرة التي مركزها $({h},{k})$ وتمرّ بالنقطة $({p},{q})$.",
        answer,
        wrong,
        (
            "طول نصف القطر هو المسافة بين المركز والنقطة، ونجد مربعه بنظرية فيثاغورس: "
            f"$r^2=({minus(p, h)})^2+({minus(q, k)})^2={dx * dx}+{dy * dy}={r2}$",
            f"نعوّض $h={h}$ و$k={k}$ و$r^2={r2}$ في الصيغة القياسية $(x-h)^2+(y-k)^2=r^2$.",
            f"إذن معادلة الدائرة {answer}.",
        ),
        "A",
        circle_check(h, k, r2, points=((p, q),)),
        wrong_kinds=kinds,
    )


# «اكتشف الخطأ» في كتابة معادلة دائرة من مركزها ونقطة عليها: الزلّة → (رقم الخطوة، نوع الخطأ من ERROR_KINDS).
CIRCLE_SLIPS = {
    "mismatched": (1, "swap"),  # طرح من كل إحداثي الإحداثي الآخر للمركز
    "doubled": (2, "square"),  # ضاعف الفرقين بدل تربيعهما
    "subtracted": (3, "formula"),  # طرح المربعين بدل جمعهما
    "center_sign": (4, "sign"),  # عكس إشارتي المركز عند التعويض في الصيغة القياسية
}


def circle_item(h: int, k: int, dx: int, dy: int, slip: str) -> ErrorSpotting | None:
    """الدائرة التي مركزها (h,k) وتمرّ بـ(h+dx,k+dy): الفرقان، ثم مربعاهما، ثم r²، ثم (h، k، r²) في المعادلة."""
    step, kind = CIRCLE_SLIPS[slip]
    p, q = h + dx, k + dy
    rules: tuple[Rule, ...] = (
        (p - h, q - k),
        (ref(1, 0) ** 2, ref(1, 1) ** 2),
        (ref(2, 0) + ref(2, 1),),
        (h, k, ref(3)),
    )
    wrong: Rule = {
        "mismatched": (p - k, q - h),
        "doubled": (2 * ref(1, 0), 2 * ref(1, 1)),
        "subtracted": (ref(2, 0) - ref(2, 1),),
        "center_sign": (-h, -k, ref(3)),
    }[slip]

    def texts(rows: list[Row], slipped: bool) -> tuple[str, ...]:
        (across, up), (across2, up2), (r2,), (a, b, _) = (tuple(int(v) for v in row) for row in rows)
        from_x, from_y = (k, h) if slipped and slip == "mismatched" else (h, k)
        joined = minus(across2, up2) if slipped and slip == "subtracted" else plus(across2, up2)
        return (
            f"نطرح إحداثيي المركز من إحداثيي النقطة: ${minus(p, from_x)}={across}$ و"
            f"${minus(q, from_y)}={up}$",
            f"نربّع الفرقين: $({across})^2={across2}$ و$({up})^2={up2}$",
            f"نجد مربع طول نصف القطر بنظرية فيثاغورس: $r^2={joined}={r2}$",
            f"نعوّض في الصيغة القياسية $(x-h)^2+(y-k)^2=r^2$: {circle(a, b, r2)}",
        )

    item = spotted_values(
        "2.10",
        f"كتب طالب معادلة الدائرة التي مركزها $({h},{k})$ وتمرّ بالنقطة $({p},{q})$ {SPOT_TASK}",
        rules,
        (step, kind, wrong),
        texts,
        circle(h, k, dx * dx + dy * dy),
        {"quantity": "circle_through_point", "center": (h, k), "point": (p, q)},
    )
    # مربع طول نصف القطر المعروض موجب، فالمعادلة المعروضة معادلة دائرة
    return None if item is None or item.check["steps"][2][0] <= 0 else item


@variant("2.10", G10, example=1, registry=ERROR_SPOTTING)
def spot_error_in_circle_equation_through_point(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(CIRCLE_SLIPS))
    while True:
        item = circle_item(rng.randint(-6, 6), rng.randint(-6, 6), nz(rng, -6, 6), nz(rng, -6, 6), slip)
        if item is not None:
            return item


@variant("2.10", G10, example=3)
def circle_equation_from_diameter_endpoints(rng: random.Random) -> Problem:
    place, edge = rng.choice(ROUND_PLACES)
    h, k = rng.randint(-5, 5), rng.randint(-5, 5)
    while True:
        dx, dy = rng.randint(-5, 5), rng.randint(-5, 5)
        if dx or dy:
            break
    (x1, y1), (x2, y2), r2 = (h - dx, k - dy), (h + dx, k + dy), dx * dx + dy * dy
    answer = circle(h, k, r2)
    wrong, kinds = tagged_wrongs(
        answer,
        ("formula", circle(h, k, 4 * r2)),
        ("concept", circle(x2, y2, r2)),
        ("sign", circle(-h, -k, r2)),
        ("formula", circle(h, k, 2 * r2)),
        ("nearby", circle(h, k, r2 + 1)),
    )
    return Problem(
        "2.10",
        f"على مخطط إحداثي لحديقة عامة، تقع نهايتا قطر {place} عند النقطتين $({x1},{y1})$ و$({x2},{y2})$. "
        f"اكتب معادلة الدائرة التي تمثّل {edge}.",
        answer,
        wrong,
        (
            "مركز الدائرة نقطة منتصف القطر: "
            f"$\\left(\\dfrac{{{plus(x1, x2)}}}{{2}},\\dfrac{{{plus(y1, y2)}}}{{2}}\\right)=({h},{k})$",
            "مربع طول نصف القطر مربع المسافة بين المركز وإحدى نهايتي القطر: "
            f"$r^2=({minus(x2, h)})^2+({minus(y2, k)})^2={r2}$",
            f"إذن معادلة الدائرة {answer}.",
        ),
        "A",
        circle_check(h, k, r2, points=((x1, y1), (x2, y2)), diameter=True),
        wrong_kinds=kinds,
    )


@variant("2.10", G10, example=3)
def point_position_relative_to_circle(rng: random.Random) -> Problem:
    h, k, r2 = rng.randint(-5, 5), rng.randint(-5, 5), rng.choice(CIRCLE_SQUARES)
    dx, dy = rng.choice(SLANTED[r2])
    position = rng.choice(list(POSITIONS))
    # إزاحة أفقية بوحدة نحو المركز تُدخل النقطة، وبوحدة بعيدًا عنه تُخرجها.
    dx += {"on": 0, "inside": -1, "outside": 1}[position] * (1 if dx > 0 else -1)
    p, q, d2 = h + dx, k + dy, dx * dx + dy * dy
    sign, word = RELATIONS[position]
    answer = POSITIONS[position]
    wrong = (*[text for name, text in POSITIONS.items() if name != position], "هي مركز الدائرة")
    return Problem(
        "2.10",
        f"حدّد موقع النقطة $({p},{q})$ بالنسبة إلى الدائرة {circle(h, k, r2)}: هل تقع على الدائرة أم "
        "داخلها أم خارجها؟",
        answer,
        wrong,
        (
            f"نعوّض $x={p}$ و$y={q}$ في الطرف الأيسر من المعادلة: "
            f"$({minus(p, h)})^2+({minus(q, k)})^2={dx * dx}+{dy * dy}={d2}$",
            f"${d2}{sign}{r2}$، أي أن مربع بُعد النقطة عن المركز {word} مربع طول نصف القطر، إذن النقطة "
            f"{answer}.",
        ),
        "A",
        {
            "type": "circle_position",
            "center": (h, k),
            "radius2": r2,
            "point": (p, q),
            "position": position,
        },
        wrong_kinds=("concept", "concept", "concept"),
    )


@variant("2.10", G10, example=5)
def solve_line_and_circle_system(rng: random.Random) -> Problem:
    r2, slope, c, first, second = rng.choice(LINE_CIRCLE_SYSTEMS)
    line = slope * x + c
    answer = points(first, second)
    wrong, kinds = point_wrongs(answer, first, second)
    return Problem(
        "2.10",
        f"حلّ النظام الخطي-التربيعي $y={tex(line)}$ و$x^2+y^2={r2}$.",
        answer,
        wrong,
        (
            f"نعوّض ${tex(line)}$ بدل $y$ في معادلة الدائرة: $x^2+({tex(line)})^2={r2}$",
            f"نفكّ المربع ونجمع الحدود المتشابهة: ${tex(sp.expand(x**2 + line**2 - r2))}=0$",
            f"نقسم طرفي المعادلة على ${1 + slope * slope}$ ونحلّل إلى العوامل: "
            f"${product(first[0], second[0])}=0$، إذن {solutions(first[0], second[0])}",
            back_substitution(slope, c, first[0], second[0]),
            f"إذن حلّا النظام {answer}.",
        ),
        "A",
        {"type": "system", "equations": (y - line, x**2 + y**2 - r2), "solutions": (first, second)},
        wrong_kinds=kinds,
    )


# الوحدة 3، تشابه المثلثات: 3.3 تشابه المثلثات، 3.4 تشابه المثلثات القائمة، 3.5 المستقيمات المتوازية والتناسب.
# المسائل بلا رسم؛ الأشكال موصوفة بأسماء الرؤوس والأطوال في النص. أمثلة الكتاب الإثرائية بلا صيغ: 3.3 (1 و2)،
# 3.4 (6)، 3.5 (4 و5: نظرية منصّف الزاوية).
CM, METER = "سم", "م"
LETTERS = ("A", "B", "C", "D", "E")
LETTER_SETS = (LETTERS, ("P", "Q", "R", "S", "T"), ("K", "L", "M", "N", "X"))


def triangle(name: str) -> str:
    return rf"\triangle {name}"


def lengths(value: Any, unit: str = CM) -> str:
    return with_unit(sp.nsimplify(value), unit)


def tagged_lengths(
    value: Any, *pairs: tuple[str, Any], unit: str = CM
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """ثلاثة بدائل أطوال موجبة مختلفة عن الجواب، كل مرشَّح مع نوع خطئه؛ ما أُضيف تتمةً «nearby»."""
    seen, texts, kinds = {sp.nsimplify(value)}, [], []
    fillers = tuple(("nearby", c) for c in (value + 1, value - 1, value + 2, 2 * value, value + 3, value - 2))
    for kind, candidate in (*pairs, *fillers):
        shown = sp.nsimplify(candidate)
        if shown > 0 and shown not in seen:
            seen.add(shown)
            texts.append(lengths(shown, unit))
            kinds.append(kind)
    return tuple(texts[:3]), tuple(kinds[:3])


def reduced_pair(rng: random.Random, low: int, high: int) -> tuple[int, int]:
    """نسبة u:v بعددين صحيحين أوليين فيما بينهما ومختلفين."""
    while True:
        u, v = rng.randint(low, high), rng.randint(low, high)
        if u != v and math.gcd(u, v) == 1:
            return u, v


# الدرس 3.3: تشابه المثلثات
CRITERIA = {
    "AA": "تطابق زاويتين (AA)",
    "SSS": "تناسب أطوال الأضلاع الثلاثة (SSS)",
    "SAS": "تناسب طولي ضلعين وتساوي الزاوية المحصورة بينهما (SAS)",
}
NOT_ENOUGH = "المعطيات لا تكفي لإثبات التشابه"
SIDE_TRIPLES = (
    (3, 4, 5),
    (4, 5, 6),
    (4, 6, 7),
    (5, 6, 7),
    (5, 7, 9),
    (6, 7, 8),
    (6, 8, 9),
    (7, 8, 10),
    (5, 8, 10),
    (7, 9, 11),
)
FACTORS = (2, 3, 4, 5)
NAMES = (("A", "B", "C"), ("D", "E", "F"), ("K", "L", "M"), ("P", "Q", "R"), ("X", "Y", "Z"))


def pair_of_triangles(rng: random.Random) -> tuple[tuple[str, str, str], tuple[str, str, str]]:
    first, second = rng.sample(NAMES, 2)
    return first, second


@variant("3.3", G10, example=3)
def triangle_similarity_criterion(rng: random.Random) -> Problem:
    (a1, b1, c1), (a2, b2, c2) = pair_of_triangles(rng)
    kind = rng.choice(list(CRITERIA))
    k = rng.choice(FACTORS)
    question = "ما المبرهنة التي تُستعمل لإثبات أن المثلثين متشابهان؟"
    if kind == "AA":
        first = rng.randint(35, 85)
        second = rng.choice([n for n in range(30, 95, 5) if n != first and first + n < 170])
        stem = (
            f"في المثلث ${a1}{b1}{c1}$ قياس $\\angle {a1}={first}^\\circ$ وقياس $\\angle {b1}={second}^\\circ$، "
            f"وفي المثلث ${a2}{b2}{c2}$ قياس $\\angle {b2}={first}^\\circ$ وقياس $\\angle {c2}={second}^\\circ$. {question}"
        )
        data = {"first": {"angles": (first, second)}, "second": {"angles": (first, second)}}
        reason = (
            "زاويتان في المثلث الأول تساويان زاويتين في المثلث الثاني (ليستا بالترتيب نفسه، "
            "والترتيب لا يهم في AA)."
        )
    elif kind == "SSS":
        sides = rng.choice(SIDE_TRIPLES)
        scaled = tuple(k * s for s in sides)
        stem = (
            f"في المثلث ${a1}{b1}{c1}$: ${a1}{b1}={sides[0]}$ سم و${b1}{c1}={sides[1]}$ سم و${c1}{a1}={sides[2]}$ سم. "
            f"وفي المثلث ${a2}{b2}{c2}$: ${a2}{b2}={scaled[0]}$ سم و${b2}{c2}={scaled[1]}$ سم و${c2}{a2}={scaled[2]}$ سم. "
            f"{question}"
        )
        data = {"first": {"sides": sides}, "second": {"sides": scaled}}
        reason = (
            f"النسب بين الأضلاع المتناظرة متساوية: ${scaled[0]}\\div{sides[0]}={scaled[1]}\\div{sides[1]}"
            f"={scaled[2]}\\div{sides[2]}={k}$."
        )
    else:
        p, q = rng.choice(SIDE_TRIPLES)[:2]
        angle = rng.choice(range(40, 130, 5))
        stem = (
            f"في المثلث ${a1}{b1}{c1}$: ${a1}{b1}={p}$ سم و${a1}{c1}={q}$ سم وقياس $\\angle {a1}={angle}^\\circ$. "
            f"وفي المثلث ${a2}{b2}{c2}$: ${a2}{b2}={k * p}$ سم و${a2}{c2}={k * q}$ سم وقياس $\\angle {a2}={angle}^\\circ$. "
            f"{question}"
        )
        data = {
            "first": {"sides": (p, q), "angle": angle},
            "second": {"sides": (k * p, k * q), "angle": angle},
        }
        reason = (
            f"الضلعان متناسبان: ${k * p}\\div{p}={k * q}\\div{q}={k}$، والزاوية $\\angle {a1}$ محصورة بين الضلعين "
            f"وتساوي $\\angle {a2}$."
        )
    answer = CRITERIA[kind]
    return Problem(
        "3.3",
        stem,
        answer,
        (*[CRITERIA[name] for name in CRITERIA if name != kind], NOT_ENOUGH),
        (
            "نفحص المعطيات: أي عناصر متناظرة في المثلثين معلومة (زوايا أم أضلاع)؟",
            reason,
            f"إذن المثلثان متشابهان بالمبرهنة: {answer}.",
        ),
        "K",
        {"type": "criterion", "kind": kind, **data},
        wrong_kinds=("concept", "concept", "concept"),
    )


@variant("3.3", G10, example=4)
def missing_side_in_similar_triangles(rng: random.Random) -> Problem:
    (a1, b1, c1), (a2, b2, c2) = pair_of_triangles(rng)
    k = rng.choice([2, 3, 4, sp.Rational(3, 2), sp.Rational(5, 2)])
    step = 2 if isinstance(k, sp.Rational) else 1
    p, q = rng.sample([n for n in range(4, 15) if n % step == 0], 2)
    big_p, big_q = k * p, k * q
    wrong, kinds = tagged_lengths(
        big_q,
        ("formula", q + (big_p - p)),
        ("concept", big_p + q),
        ("formula", sp.Rational(q) / k),
    )
    return Problem(
        "3.3",
        f"المثلثان ${a1}{b1}{c1}$ و${a2}{b2}{c2}$ متشابهان ($\\triangle {a1}{b1}{c1}\\sim\\triangle {a2}{b2}{c2}$). "
        f"إذا كان ${a1}{b1}={p}$ سم و${b1}{c1}={q}$ سم و${a2}{b2}={big_p}$ سم، فما طول ${b2}{c2}$؟",
        lengths(big_q),
        wrong,
        (
            "الأضلاع المتناظرة في المثلثين المتشابهين متناسبة: "
            f"$\\dfrac{{{a2}{b2}}}{{{a1}{b1}}}=\\dfrac{{{b2}{c2}}}{{{b1}{c1}}}$",
            f"نعوّض: $\\dfrac{{{big_p}}}{{{p}}}=\\dfrac{{{b2}{c2}}}{{{q}}}$، فمعامل التكبير $\\dfrac{{{big_p}}}{{{p}}}={tex(k)}$.",
            f"${b2}{c2}={tex(k)}\\times {q}={tex(big_q)}$ سم.",
        ),
        "K",
        {"type": "similar_sides", "first": (p, q), "second": (big_p, big_q), "asked": 1},
        wrong_kinds=kinds,
    )


@variant("3.3", G10, example=4)
def perimeter_of_similar_triangle(rng: random.Random) -> Problem:
    (a1, b1, c1), (a2, b2, c2) = pair_of_triangles(rng)
    k = rng.choice([2, 3, 4, 5, sp.Rational(3, 2), sp.Rational(5, 2)])
    mult = 2 if isinstance(k, sp.Rational) else 1
    base = tuple(s * mult for s in rng.choice(SIDE_TRIPLES))
    scale_up = tuple(k * s for s in base)
    perimeter, big_perimeter = sum(base), sum(scale_up)
    wrong, kinds = tagged_lengths(
        big_perimeter,
        ("concept", perimeter),
        ("formula", scale_up[0] + base[1] + base[2]),
        ("formula", perimeter + 3 * (scale_up[0] - base[0])),
    )
    return Problem(
        "3.3",
        f"المثلث ${a1}{b1}{c1}$ أطوال أضلاعه ${base[0]}$ سم و${base[1]}$ سم و${base[2]}$ سم، وهو يشابه المثلث "
        f"${a2}{b2}{c2}$ حيث ${a2}{b2}$ يناظر ${a1}{b1}$ وطوله ${scale_up[0]}$ سم. أوجد محيط المثلث ${a2}{b2}{c2}$.",
        lengths(big_perimeter),
        wrong,
        (
            f"معامل التشابه بين الضلعين المتناظرين: $\\dfrac{{{scale_up[0]}}}{{{base[0]}}}={tex(k)}$",
            f"محيط المثلث ${a1}{b1}{c1}$ يساوي ${base[0]}+{base[1]}+{base[2]}={perimeter}$ سم.",
            f"النسبة بين محيطي مثلثين متشابهين تساوي معامل التشابه، فمحيط ${a2}{b2}{c2}$ يساوي "
            f"${tex(k)}\\times {perimeter}={big_perimeter}$ سم.",
        ),
        "A",
        {"type": "similar_sides", "first": base, "second": scale_up, "perimeter": (perimeter, big_perimeter)},
        wrong_kinds=kinds,
    )


@variant("3.3", G10, example=4)
def side_from_similar_triangles_algebraic(rng: random.Random) -> Problem:
    (a1, b1, c1), (a2, b2, c2) = pair_of_triangles(rng)
    while True:
        k, q = rng.choice([2, 3]), rng.randint(2, 9)
        p, x0, m = rng.randint(1, 4), rng.randint(2, 9), rng.randint(k + 1, k + 3)
        n = (m - k) * x0 - k * p
        if n >= 1:
            break
    first, second = x + p, m * x - n
    shown_first, shown_second = f"x+{p}", f"{m}x-{n}"
    value = k * (x0 + p)
    wrong, kinds = tagged_lengths(
        value,
        ("partial", x0),
        ("partial", x0 + p),
        ("formula", k * x0),
    )
    return Problem(
        "3.3",
        f"المثلثان ${a1}{b1}{c1}$ و${a2}{b2}{c2}$ متشابهان ($\\triangle {a1}{b1}{c1}\\sim\\triangle {a2}{b2}{c2}$). "
        f"إذا كان ${a1}{b1}={shown_first}$ سم و${a2}{b2}={shown_second}$ سم و${b1}{c1}={q}$ سم و${b2}{c2}={k * q}$ سم، "
        f"فما طول ${a2}{b2}$؟",
        lengths(value),
        wrong,
        (
            "الأضلاع المتناظرة متناسبة: "
            f"$\\dfrac{{{a1}{b1}}}{{{a2}{b2}}}=\\dfrac{{{b1}{c1}}}{{{b2}{c2}}}$، "
            f"أي $\\dfrac{{{shown_first}}}{{{shown_second}}}=\\dfrac{{{q}}}{{{k * q}}}=\\dfrac{{1}}{{{k}}}$",
            f"نضرب طرفًا في وسط: ${k}({shown_first})={shown_second}$، أي ${k}x+{k * p}={m}x-{n}$",
            f"نحلّ المعادلة: ${m - k}x={k * p + n}$، إذن $x={x0}$.",
            f"${a2}{b2}={m}({x0})-{n}={value}$ سم.",
        ),
        "A",
        {
            "type": "similar_algebra",
            "proportion": (first, second, q, k * q),
            "x": x0,
            "value": value,
            "expr": second,
        },
        wrong_kinds=kinds,
    )


# (الجسم المطلوب ارتفاعه، الجسم المعلوم، ضمير ارتفاع المعلوم)
SHADOW_SCENES = (
    ("عمود إنارة", "عصا", "ها"),
    ("شجرة", "عمود", "ه"),
    ("برج اتصالات", "لوحة", "ها"),
    ("مبنى", "سارية", "ها"),
    ("جدار", "كرسي", "ه"),
)


@variant("3.3", G10, example=5)
def height_from_shadows(rng: random.Random) -> Problem:
    target, known, pronoun = rng.choice(SHADOW_SCENES)
    h, s = rng.choice([(1, 2), (2, 3), (3, 2), (2, 5), (3, 4), (4, 3), (5, 4), (3, 5), (6, 5)])
    t = rng.randint(3, 14)
    big_h, big_s = h * t, s * t
    wrong, kinds = tagged_lengths(
        big_h,
        ("formula", big_s + h - s),
        ("formula", big_s - h),
        ("formula", big_s - s),
        unit=METER,
    )
    return Problem(
        "3.3",
        f"في اللحظة نفسها من النهار، يبلغ طول ظل {known} ارتفاع{pronoun} ${h}$ م ما مقداره ${s}$ م، "
        f"ويبلغ طول ظل {target} ما مقداره ${big_s}$ م. ما ارتفاع {target}؟",
        lengths(big_h, METER),
        wrong,
        (
            "أشعة الشمس متوازية، فالمثلثان القائمان (الجسم وظله) فيهما زاوية ارتفاع الشمس نفسها وزاوية قائمة، "
            "فهما متشابهان بتطابق زاويتين.",
            f"نسبة الارتفاع إلى الظل واحدة في المثلثين. نفرض ارتفاع {target} $=y$: "
            f"$\\dfrac{{{h}}}{{{s}}}=\\dfrac{{y}}{{{big_s}}}$",
            f"$y=\\dfrac{{{h}\\times {big_s}}}{{{s}}}={big_h}$ م.",
        ),
        "A",
        {"type": "proportion", "pairs": ((h, s), (big_h, big_s)), "value": big_h},
        wrong_kinds=kinds,
    )


# «اكتشف الخطأ» في محيط مثلث من مثلث يشابهه: الزلّة → (رقم الخطوة، نوع الخطأ من ERROR_KINDS).
SIMILAR_PERIMETER_SLIPS = {
    "inverted": (1, "swap"),  # قلب نسبة الضلعين المتناظرين
    "added": (2, "formula"),  # أضاف فرق الضلعين بدل الضرب في معامل التشابه
    "missing": (3, "partial"),  # جمع الضلعين المحسوبين وترك الضلع المعطى
}


def similar_perimeter_item(
    first: tuple[str, str, str],
    second: tuple[str, str, str],
    base: tuple[int, int, int],
    big: int,
    slip: str,
) -> ErrorSpotting | None:
    """مثلثان متشابهان: أضلاع الأول معلومة وأول أضلاع الثاني big؛ المعامل، ثم الضلعان الباقيان، ثم المحيط."""
    step, kind = SIMILAR_PERIMETER_SLIPS[slip]
    p, q, r = base
    rules: tuple[Rule, ...] = (
        (sp.Rational(big, p),),
        (ref(1) * q, ref(1) * r),
        (big + ref(2, 0) + ref(2, 1),),
    )
    wrong: Rule = {
        "inverted": (sp.Rational(p, big),),
        "added": (q + big - p, r + big - p),
        "missing": (ref(2, 0) + ref(2, 1),),
    }[slip]
    (a1, b1, c1), (a2, b2, c2) = first, second

    def texts(rows: list[Row], slipped: bool) -> tuple[str, ...]:
        (k,), (side_q, side_r), (total,) = rows
        top, bottom = (p, big) if slipped and slip == "inverted" else (big, p)
        if slipped and slip == "added":
            sides = f"${b2}{c2}={q}+({big}-{p})={tex(side_q)}$ و${c2}{a2}={r}+({big}-{p})={tex(side_r)}$"
        else:
            sides = (
                f"${b2}{c2}={tex(k)}\\times {q}={tex(side_q)}$ و${c2}{a2}={tex(k)}\\times {r}={tex(side_r)}$"
            )
        terms = [side_q, side_r] if slipped and slip == "missing" else [big, side_q, side_r]
        return (
            f"نجد معامل التشابه من ${a1}{b1}$ إلى ${a2}{b2}$: $k=\\dfrac{{{top}}}{{{bottom}}}={tex(k)}$",
            f"نجد الضلعين الباقيين: {sides}",
            f"نجمع لإيجاد المحيط: ${'+'.join(tex(term) for term in terms)}={tex(total)}$ سم",
        )

    return spotted_values(
        "3.3",
        f"حسب طالب محيط المثلث ${a2}{b2}{c2}$، علمًا بأن $\\triangle {a1}{b1}{c1}\\sim\\triangle {a2}{b2}{c2}$ "
        f"و${a1}{b1}={p}$ سم و${b1}{c1}={q}$ سم و${c1}{a1}={r}$ سم و${a2}{b2}={big}$ سم، {SPOT_TASK}",
        rules,
        (step, kind, wrong),
        texts,
        lengths(sp.Rational(big * (p + q + r), p)),
        {"quantity": "similar_perimeter", "base": base, "big": big},
    )


@variant("3.3", G10, example=4, registry=ERROR_SPOTTING)
def spot_error_in_perimeter_of_similar_triangle(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(SIMILAR_PERIMETER_SLIPS))
    while True:
        first, second = pair_of_triangles(rng)
        k = rng.choice([2, 3, 4, sp.Rational(3, 2), sp.Rational(5, 2)])
        mult = 2 if isinstance(k, sp.Rational) else 1
        p, q, r = (s * mult for s in rng.choice(SIDE_TRIPLES))
        item = similar_perimeter_item(first, second, (p, q, r), int(k * p), slip)
        if item is not None:
            return item


# الدرس 3.4: تشابه المثلثات القائمة والمتوسط الهندسي
RIGHT_NAMES = (("A", "B", "C", "D"), ("P", "Q", "R", "S"), ("K", "L", "M", "N"), ("X", "Y", "Z", "W"))
# (u, v، المقياس): AD=s·u² وDB=s·v² وu²+v² مربع كامل، فكل أطوال الشكل أعداد صحيحة.
PROJECTION_SHAPES = (
    tuple(((3, 4), s) for s in (1, 2, 3, 4))
    + tuple(((4, 3), s) for s in (1, 2, 3, 4))
    + (
        ((6, 8), 1),
        ((8, 6), 1),
    )
)
# أزواج (AD, DB) جداؤها مربع كامل: (a·u², a·v²)
SQUARE_PRODUCT_PAIRS = tuple(
    (a * u * u, a * v * v)
    for a in (1, 2, 3, 5)
    for u, v in ((1, 2), (1, 3), (2, 3), (1, 4), (2, 5), (3, 4), (1, 5), (3, 5))
    if a * v * v <= 90
)


def right_triangle_values(shape: tuple[tuple[int, int], int]) -> dict[str, int]:
    """مثلث قائم الزاوية عند C وD أسفل العمود منه على الوتر: أطوال كل القطع أعداد صحيحة بالبناء."""
    (u, v), scale_ = shape
    ad, db, hypotenuse = scale_ * u * u, scale_ * v * v, math.isqrt(u * u + v * v)
    return {
        "AD": ad,
        "DB": db,
        "CD": scale_ * u * v,
        "AB": ad + db,
        "AC": scale_ * u * hypotenuse,
        "BC": scale_ * v * hypotenuse,
    }


def legs_for_angle(degrees: int, at_a: bool) -> tuple[float, float]:
    """(AC, BC) لمثلث قائم في C وتره 1 وقياس الزاوية عند A (أو عند B) بالدرجات المعطاة."""
    adjacent, opposite = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return (adjacent, opposite) if at_a else (opposite, adjacent)


@variant("3.4", G10, example=1)
def similarity_statement_with_altitude(rng: random.Random) -> Problem:
    a, b, c, d = rng.choice(RIGHT_NAMES)
    common = rng.choice([a, b])
    degrees = rng.randint(25, 65)
    # abc قائم في c، وd أسفل العمود من c على ab: abc ~ acd (الزاوية a مشتركة) وabc ~ cbd (الزاوية b مشتركة).
    sequence = (a, c, d) if common == a else (c, b, d)
    mapping = f"${a}\\to {sequence[0]}$ و${b}\\to {sequence[1]}$ و${c}\\to {sequence[2]}$"
    orders = [order for order in itertools.permutations(sequence) if order != sequence]
    rng.shuffle(orders)
    options = [f"${triangle(''.join(order))}$" for order in orders]
    return Problem(
        "3.4",
        f"في المثلث ${a}{b}{c}$ القائم الزاوية في ${c}$ رُسم العمود ${c}{d}$ على الوتر ${a}{b}$ (حيث ${d}$ على ${a}{b}$). "
        f"أكمل عبارة التشابه بالترتيب الصحيح للرؤوس المتناظرة: $\\triangle {a}{b}{c}\\sim$ ... "
        f"علمًا بأن الزاوية ${common}$ مشتركة بين المثلثين وقياسها ${degrees}^\\circ$.",
        f"${triangle(''.join(sequence))}$",
        tuple(options[:3]),
        (
            f"المثلثان قائمان: القائمة في ${triangle(a + b + c)}$ عند ${c}$، وفي المثلث الآخر عند ${d}$ "
            f"(لأن ${c}{d}\\perp {a}{b}$).",
            f"الزاوية ${common}$ مشتركة، فالمثلثان متشابهان بتطابق زاويتين، والرؤوس المتناظرة: {mapping}.",
            f"إذن $\\triangle {a}{b}{c}\\sim{triangle(''.join(sequence))}$.",
        ),
        "K",
        {
            "type": "similarity_statement",
            # ساقان بوتر واحد تجعلان قياس الزاوية المشتركة المذكورة في النص
            "legs": legs_for_angle(degrees, common == a),
            "names": (a, b, c, d),
            "answer": sequence,
            "wrong": tuple(orders[:3]),
        },
        wrong_kinds=("swap", "swap", "swap"),
    )


@variant("3.4", G10, example=2)
def leg_from_projection(rng: random.Random) -> Problem:
    values = right_triangle_values(rng.choice(PROJECTION_SHAPES))
    a, b, c, d = rng.choice(RIGHT_NAMES)
    which = rng.choice(["AC", "BC"])
    projection = values["AD" if which == "AC" else "DB"]
    leg = values[which]
    leg_name, near = (f"{a}{c}", f"{a}{d}") if which == "AC" else (f"{b}{c}", f"{d}{b}")
    wrong, kinds = tagged_lengths(
        leg,
        ("square", projection * values["AB"]),
        ("formula", values["AB"] - projection),
        ("concept", values["CD"]),
    )
    return Problem(
        "3.4",
        f"في المثلث ${a}{b}{c}$ القائم الزاوية في ${c}$ رُسم العمود ${c}{d}$ على الوتر ${a}{b}$. "
        f"إذا كان ${near}={projection}$ سم و${a}{b}={values['AB']}$ سم، فما طول ${leg_name}$؟",
        lengths(leg),
        wrong,
        (
            "طول كل ساق هو المتوسط الهندسي بين طول الوتر وطول مسقط الساق عليه: "
            f"${leg_name}^2={near}\\times {a}{b}$",
            f"${leg_name}^2={projection}\\times {values['AB']}={projection * values['AB']}$",
            f"${leg_name}=\\sqrt{{{projection * values['AB']}}}={leg}$ سم.",
        ),
        "K",
        {
            "type": "altitude",
            "legs": (values["AC"], values["BC"]),
            "asked": which,
            "value": leg,
            "given": {"AD" if which == "AC" else "DB": projection, "AB": values["AB"]},
        },
        wrong_kinds=kinds,
    )


# «اكتشف الخطأ» في طول ساق من مسقطه على الوتر: الزلّة → (رقم الخطوة، نوع الخطأ من ERROR_KINDS).
LEG_SLIPS = {
    "one_part": (1, "partial"),  # أخذ القطعة الأخرى وحدها وترًا
    "altitude_mean": (2, "concept"),  # ضرب قطعتي الوتر (علاقة الارتفاع) بدل المسقط في الوتر
    "halved": (3, "square"),  # قسم المربع على 2 بدل أخذ جذره
}


def leg_item(
    names: tuple[str, str, str, str], values: dict[str, int], which: str, slip: str
) -> ErrorSpotting:
    """ساق من مثلث قائم ارتفاعه على الوتر: الوتر، ثم مربع الساق، ثم الساق."""
    step, kind = LEG_SLIPS[slip]
    a, b, c, d = names
    segments = {"AC": (f"{a}{d}", f"{d}{b}"), "BC": (f"{d}{b}", f"{a}{d}")}
    near, far = segments[which]
    projection, other = (values["AD"], values["DB"]) if which == "AC" else (values["DB"], values["AD"])
    leg_name = f"{a}{c}" if which == "AC" else f"{b}{c}"
    rules: tuple[Rule, ...] = ((projection + other,), (projection * ref(1),), (sp.sqrt(ref(2)),))
    wrong: Rule = {
        "one_part": (other,),
        "altitude_mean": (projection * other,),
        "halved": (ref(2) / 2,),
    }[slip]

    def texts(rows: list[Row], slipped: bool) -> tuple[str, ...]:
        (hypotenuse,), (square,), (leg,) = rows
        total = f"{other}" if slipped and slip == "one_part" else f"{near}+{far}={projection}+{other}"
        if slipped and slip == "altitude_mean":
            product_ = f"{near}\\times {far}={projection}\\times {other}"
        else:
            product_ = f"{near}\\times {a}{b}={projection}\\times {hypotenuse}"
        root_ = f"\\dfrac{{{square}}}{{2}}" if slipped and slip == "halved" else f"\\sqrt{{{square}}}"
        return (
            f"نجد طول الوتر: ${a}{b}={total}={hypotenuse}$ سم",
            f"طول الساق متوسط هندسي: ${leg_name}^2={product_}={square}$",
            f"إذن ${leg_name}={root_}={tex(leg)}$ سم",
        )

    item = spotted_values(
        "3.4",
        f"حسب طالب طول ${leg_name}$ في المثلث ${a}{b}{c}$ القائم الزاوية في ${c}$، وقد رُسم العمود ${c}{d}$ على "
        f"الوتر ${a}{b}$، حيث ${near}={projection}$ سم و${far}={other}$ سم، {SPOT_TASK}",
        rules,
        (step, kind, wrong),
        texts,
        lengths(values[which]),
        {"quantity": "leg_from_segments", "segments": (values["AD"], values["DB"]), "leg": which},
    )
    assert item is not None  # كل أطوال الشكل أعداد صحيحة، وكل زلّة تغيّر الساق
    return item


@variant("3.4", G10, example=2, registry=ERROR_SPOTTING)
def spot_error_in_leg_from_projection(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(LEG_SLIPS))
    values = right_triangle_values(rng.choice(PROJECTION_SHAPES))
    return leg_item(rng.choice(RIGHT_NAMES), values, rng.choice(["AC", "BC"]), slip)


@variant("3.4", G10, example=3)
def segment_from_similar_right_triangles(rng: random.Random) -> Problem:
    values = right_triangle_values(rng.choice(PROJECTION_SHAPES))
    a, b, c, d = rng.choice(RIGHT_NAMES)
    ac, bc, cd = values["AC"], values["BC"], values["CD"]
    asked = rng.choice(["AD", "DB"])
    value, other = (values["AD"], values["DB"]) if asked == "AD" else (values["DB"], values["AD"])
    name = f"{a}{d}" if asked == "AD" else f"{d}{b}"
    if asked == "AD":
        ratio = f"\\dfrac{{{a}{d}}}{{{c}{d}}}=\\dfrac{{{a}{c}}}{{{c}{b}}}"
        solve = f"{a}{d}=\\dfrac{{{cd}\\times {ac}}}{{{bc}}}"
    else:
        ratio = f"\\dfrac{{{c}{d}}}{{{d}{b}}}=\\dfrac{{{a}{c}}}{{{c}{b}}}"
        solve = f"{d}{b}=\\dfrac{{{cd}\\times {bc}}}{{{ac}}}"
    wrong, kinds = tagged_lengths(
        value,
        ("swap", other),
        ("concept", values["AB"]),
        ("concept", cd),
    )
    return Problem(
        "3.4",
        f"في المثلث ${a}{b}{c}$ القائم الزاوية في ${c}$ رُسم العمود ${c}{d}$ على الوتر ${a}{b}$. "
        f"إذا كان ${a}{c}={ac}$ سم و${b}{c}={bc}$ سم و${c}{d}={cd}$ سم، فاستعمل تشابه المثلثين "
        f"${a}{c}{d}$ و${c}{b}{d}$ لإيجاد طول ${name}$.",
        lengths(value),
        wrong,
        (
            f"المثلثان ${a}{c}{d}$ و${c}{b}{d}$ قائمان في ${d}$، والزاوية ${a}{c}{d}$ تطابق الزاوية ${b}$ "
            f"(كلتاهما متممة للزاوية ${a}$)، فـ $\\triangle {a}{c}{d}\\sim\\triangle {c}{b}{d}$.",
            f"الأضلاع المتناظرة متناسبة: ${ratio}$",
            f"${solve}={value}$ سم.",
        ),
        "A",
        {
            "type": "similar_right_proportion",
            "legs": (ac, bc),
            "given": {"AC": ac, "BC": bc, "CD": cd},
            "asked": asked,
            "value": value,
        },
        wrong_kinds=kinds,
    )


@variant("3.4", G10, example=4)
def altitude_as_geometric_mean(rng: random.Random) -> Problem:
    first, second = rng.sample(rng.choice(SQUARE_PRODUCT_PAIRS), 2)
    a, b, c, d = rng.choice(RIGHT_NAMES)
    height = math.isqrt(first * second)
    wrong, kinds = tagged_lengths(
        height,
        ("concept", sp.Rational(first + second, 2)),
        ("square", first * second),
        ("formula", first + second),
    )
    return Problem(
        "3.4",
        f"في المثلث ${a}{b}{c}$ القائم الزاوية في ${c}$ رُسم العمود ${c}{d}$ على الوتر ${a}{b}$. "
        f"إذا كان ${a}{d}={first}$ سم و${d}{b}={second}$ سم، فما طول ${c}{d}$؟",
        lengths(height),
        wrong,
        (
            "طول العمود النازل من رأس القائمة على الوتر هو المتوسط الهندسي بين طولي قطعتي الوتر: "
            f"${c}{d}^2={a}{d}\\times {d}{b}$",
            f"${c}{d}^2={first}\\times {second}={first * second}$",
            f"${c}{d}=\\sqrt{{{first * second}}}={height}$ سم.",
        ),
        "K",
        {"type": "geometric_mean", "parts": (first, second), "value": height},
        wrong_kinds=kinds,
    )


@variant("3.4", G10, example=4)
def altitude_from_two_legs(rng: random.Random) -> Problem:
    values = right_triangle_values(((3, 4), rng.randint(1, 6)))
    a, b, c, d = rng.choice(RIGHT_NAMES)
    first, second = rng.sample((values["AC"], values["BC"]), 2)
    height, hypotenuse = values["CD"], values["AB"]
    projection = sp.Rational(first * first, hypotenuse)
    wrong, kinds = tagged_lengths(
        height,
        ("formula", sp.Rational(first * second, 2)),
        ("formula", first + second - hypotenuse),
        ("concept", projection),
    )
    return Problem(
        "3.4",
        f"في المثلث ${a}{b}{c}$ القائم الزاوية في ${c}$ رُسم العمود ${c}{d}$ على الوتر ${a}{b}$. "
        f"إذا كان ${a}{c}={first}$ سم و${b}{c}={second}$ سم، فما طول ${c}{d}$؟",
        lengths(height),
        wrong,
        (
            f"نجد الوتر بنظرية فيثاغورس: ${a}{b}=\\sqrt{{{first}^2+{second}^2}}={hypotenuse}$ سم.",
            f"من ${a}{c}^2={a}{d}\\times {a}{b}$ نجد مسقط ${a}{c}$ على الوتر: "
            f"${a}{d}=\\dfrac{{{first}^2}}{{{hypotenuse}}}={tex(projection)}$ سم، "
            f"و${d}{b}={hypotenuse}-{tex(projection)}={tex(hypotenuse - projection)}$ سم.",
            f"${c}{d}^2={a}{d}\\times {d}{b}={tex(projection * (hypotenuse - projection))}$، إذن ${c}{d}={height}$ سم.",
        ),
        "A",
        {"type": "altitude", "legs": (first, second), "asked": "CD", "value": height},
        wrong_kinds=kinds,
    )


# (المكان، ما يُنشأ عموديًا على الوتر، اسمه)
PATH_SCENES = (
    ("حديقة مثلثة قائمة الزاوية", "ممرٌّ مستقيم", "هذا الممر"),
    ("قطعة أرض مثلثة قائمة الزاوية", "سورٌ فاصل", "هذا السور"),
    ("لوحة إعلانات مثلثة قائمة الزاوية", "دعامةٌ مستقيمة", "هذه الدعامة"),
)


@variant("3.4", G10, example=5)
def geometric_mean_in_context(rng: random.Random) -> Problem:
    first, second = rng.sample(rng.choice(SQUARE_PRODUCT_PAIRS), 2)
    place, support, short = rng.choice(PATH_SCENES)
    total, height = first + second, math.isqrt(first * second)
    wrong, kinds = tagged_lengths(
        height,
        ("concept", sp.Rational(total, 2)),
        ("square", first * second),
        ("formula", total),
        unit=METER,
    )
    return Problem(
        "3.4",
        f"في {place} أُنشئ {support} من رأس الزاوية القائمة عموديًا على الوتر، فقسم الوتر إلى قطعتين "
        f"طولاهما ${first}$ م و${second}$ م. ما طول {short}؟",
        lengths(height, METER),
        wrong,
        (
            "المثلثان الصغيران الناتجان عن الخط العمودي متشابهان مع المثلث الكبير، فطول الخط هو المتوسط الهندسي "
            "بين طولي قطعتي الوتر.",
            f"الطول $=\\sqrt{{{first}\\times {second}}}=\\sqrt{{{first * second}}}={height}$ م.",
        ),
        "A",
        {"type": "geometric_mean", "parts": (first, second), "value": height},
        wrong_kinds=kinds,
    )


# الدرس 3.5: المستقيمات المتوازية وتناسب الأضلاع (منصّف الزاوية: المثالان 4 و5 إثرائيان فلا صيغ لهما)
def parallel_values(rng: random.Random, small: int = 2, large: int = 7) -> tuple[int, int, int, int]:
    """(AD, DB, AE, EC) بنسبة واحدة u:v؛ DE موازٍ لـ BC."""
    u, v = reduced_pair(rng, small, large)
    s, t = rng.randint(1, 3), rng.randint(1, 3)
    return u * s, v * s, u * t, v * t


@variant("3.5", G10, example=1)
def segment_from_parallel_line(rng: random.Random) -> Problem:
    ad, db, ae, ec = parallel_values(rng)
    a, b, c, d, e = rng.choice(LETTER_SETS)
    given = {"AD": ad, "DB": db, "AE": ae, "EC": ec}
    names = {"AD": f"{a}{d}", "DB": f"{d}{b}", "AE": f"{a}{e}", "EC": f"{e}{c}"}
    unknown = rng.choice(["EC", "DB", "AE"])
    top, bottom_one, bottom_two = (
        given[n]
        for n in {"EC": ("AE", "DB", "AD"), "DB": ("AD", "EC", "AE"), "AE": ("AD", "EC", "DB")}[unknown]
    )
    value = given[unknown]
    facts = " و".join(f"${names[n]}={given[n]}$ سم" for n in given if n != unknown)

    def label(n: str) -> str:
        return names[n] if n == unknown else str(given[n])

    wrong, kinds = tagged_lengths(
        value,
        ("formula", top + bottom_one - bottom_two),
        ("swap", sp.Rational(top * bottom_two, bottom_one)),
        ("swap", sp.Rational(bottom_one * bottom_two, top)),
    )
    return Problem(
        "3.5",
        f"في المثلث ${a}{b}{c}$ تقع النقطة ${d}$ على ${a}{b}$ والنقطة ${e}$ على ${a}{c}$، والقطعة ${d}{e}$ توازي ${b}{c}$. "
        f"إذا كان {facts}، فما طول ${names[unknown]}$؟",
        lengths(value),
        wrong,
        (
            "المستقيم الموازي لأحد أضلاع المثلث يقسم الضلعين الآخرين إلى أجزاء متناسبة: "
            f"$\\dfrac{{{a}{d}}}{{{d}{b}}}=\\dfrac{{{a}{e}}}{{{e}{c}}}$",
            f"نعوّض: $\\dfrac{{{label('AD')}}}{{{label('DB')}}}=\\dfrac{{{label('AE')}}}{{{label('EC')}}}$",
            f"نضرب طرفًا في وسط: ${names[unknown]}=\\dfrac{{{top}\\times {bottom_one}}}{{{bottom_two}}}={value}$ سم.",
        ),
        "K",
        {"type": "parallel_division", "values": given, "asked": unknown, "value": value},
        wrong_kinds=kinds,
    )


# «اكتشف الخطأ» في طول ضلع يقطعه مستقيم مواز: الزلّة → (رقم الخطوة، نوع الخطأ من ERROR_KINDS).
PARALLEL_SLIPS = {
    "whole_ratio": (1, "concept"),  # نسبة الجزء إلى الضلع كله بدل الجزء إلى الجزء
    "inverted": (2, "swap"),  # ضرب في النسبة بدل القسمة عليها
    "one_part": (3, "partial"),  # اكتفى بالقطعة المحسوبة دون جمعها
}


def parallel_side_item(names: tuple[str, ...], ad: int, db: int, ae: int, slip: str) -> ErrorSpotting | None:
    """DE موازٍ لـ BC: النسبة AD/DB، ثم EC، ثم AC."""
    step, kind = PARALLEL_SLIPS[slip]
    a, b, c, d, e = names
    rules: tuple[Rule, ...] = ((sp.Rational(ad, db),), (ae / ref(1),), (ae + ref(2),))
    wrong: Rule = {
        "whole_ratio": (sp.Rational(ad, ad + db),),
        "inverted": (ae * ref(1),),
        "one_part": (ref(2),),
    }[slip]

    def texts(rows: list[Row], slipped: bool) -> tuple[str, ...]:
        (ratio,), (ec,), (side,) = rows
        bottom = f"{ad}+{db}" if slipped and slip == "whole_ratio" else f"{db}"
        operation = r"\times " if slipped and slip == "inverted" else r"\div "
        total = tex(ec) if slipped and slip == "one_part" else f"{ae}+{tex(ec)}={tex(side)}"
        return (
            f"نجد نسبة القطعتين على ${a}{b}$: $\\dfrac{{{a}{d}}}{{{d}{b}}}=\\dfrac{{{ad}}}{{{bottom}}}={tex(ratio)}$",
            f"من التناسب: ${e}{c}={ae}{operation}{tex(ratio)}={tex(ec)}$ سم",
            f"إذن ${a}{c}={total}$ سم",
        )

    return spotted_values(
        "3.5",
        f"حسب طالب طول ${a}{c}$ في المثلث ${a}{b}{c}$، حيث ${d}$ على ${a}{b}$ و${e}$ على ${a}{c}$ و"
        f"${d}{e}\\parallel {b}{c}$ و${a}{d}={ad}$ سم و${d}{b}={db}$ سم و${a}{e}={ae}$ سم، {SPOT_TASK}",
        rules,
        (step, kind, wrong),
        texts,
        lengths(sp.Rational(ae * (ad + db), ad)),
        {"quantity": "parallel_side", "AD": ad, "DB": db, "AE": ae},
    )


@variant("3.5", G10, example=1, registry=ERROR_SPOTTING)
def spot_error_in_side_cut_by_parallel(rng: random.Random) -> ErrorSpotting:
    slip = rng.choice(sorted(PARALLEL_SLIPS))
    while True:
        ad, db, ae, _ = parallel_values(rng)
        item = parallel_side_item(rng.choice(LETTER_SETS), ad, db, ae, slip)
        if item is not None:
            return item


@variant("3.5", G10, example=3)
def midsegment_length(rng: random.Random) -> Problem:
    a, b, c, d, e = rng.choice(LETTER_SETS)
    half = rng.randint(3, 25)
    base = 2 * half
    know_base = rng.choice([True, False])
    value, given = (half, base) if know_base else (base, half)
    given_text = f"${b}{c}={base}$ سم" if know_base else f"${d}{e}={half}$ سم"
    asked_name = f"{d}{e}" if know_base else f"{b}{c}"
    wrong, kinds = tagged_lengths(
        value,
        ("concept", given),
        ("formula", base + half),
        ("formula", abs(base - half)),
    )
    return Problem(
        "3.5",
        f"في المثلث ${a}{b}{c}$ النقطة ${d}$ منتصف ${a}{b}$ والنقطة ${e}$ منتصف ${a}{c}$. "
        f"إذا كان {given_text}، فما طول ${asked_name}$؟",
        lengths(value),
        wrong,
        (
            f"القطعة ${d}{e}$ تصل بين منتصفي ضلعين في المثلث، فهي توازي الضلع الثالث وطولها نصف طوله: "
            f"${d}{e}=\\dfrac{{1}}{{2}}{b}{c}$",
            f"إذن ${asked_name}={value}$ سم.",
        ),
        "K",
        {
            "type": "midsegment",
            "base": base,
            "mid": half,
            "asked": "DE" if know_base else "BC",
            "value": value,
        },
        wrong_kinds=kinds,
    )


@variant("3.5", G10, example=3)
def parallel_line_with_whole_side(rng: random.Random) -> Problem:
    ad, db, ae, ec = parallel_values(rng, 2, 6)
    a, b, c, d, e = rng.choice(LETTER_SETS)
    whole, side = ad + db, ae + ec
    unknown = rng.choice(["AE", "EC", "AC"])
    value = {"AE": ae, "EC": ec, "AC": side}[unknown]
    names = {"AE": f"{a}{e}", "EC": f"{e}{c}", "AC": f"{a}{c}"}
    if unknown == "AC":
        given = f"${a}{d}={ad}$ سم و${a}{b}={whole}$ سم و${a}{e}={ae}$ سم"
        wrong = (sp.Rational(ae * db, ad), ae + db, sp.Rational(ae * ad, whole))
        finish = f"${a}{c}={a}{e}+{e}{c}={ae}+{ec}={side}$ سم."
        method = (
            f"من التناسب $\\dfrac{{{a}{d}}}{{{d}{b}}}=\\dfrac{{{a}{e}}}{{{e}{c}}}$ نجد "
            f"${e}{c}=\\dfrac{{{ae}\\times {db}}}{{{ad}}}={ec}$ سم."
        )
    else:
        given = f"${a}{d}={ad}$ سم و${a}{b}={whole}$ سم و${a}{c}={side}$ سم"
        wrong = (
            (sp.Rational(side * ad, db), side - ad, sp.Rational(side * db, whole))
            if unknown == "AE"
            else (sp.Rational(side * db, ad), ae, side - db)
        )
        method = (
            f"نفرض ${a}{e}=y$ فيكون ${e}{c}={side}-y$، ومن التناسب "
            f"$\\dfrac{{{ad}}}{{{db}}}=\\dfrac{{y}}{{{side}-y}}$ نجد ${db}y={ad}({side}-y)$، أي ${whole}y={ad * side}$، "
            f"إذن ${a}{e}={ae}$ سم."
        )
        finish = f"${a}{e}={ae}$ سم." if unknown == "AE" else f"${e}{c}={a}{c}-{a}{e}={side}-{ae}={ec}$ سم."
    texts, kinds = tagged_lengths(value, *[("formula", w) for w in wrong])
    return Problem(
        "3.5",
        f"في المثلث ${a}{b}{c}$ تقع ${d}$ على ${a}{b}$ و${e}$ على ${a}{c}$ والقطعة ${d}{e}$ توازي ${b}{c}$. "
        f"إذا كان {given}، فما طول ${names[unknown]}$؟",
        lengths(value),
        texts,
        (
            f"نجد ${d}{b}={a}{b}-{a}{d}={db}$ سم، ثم نستعمل التناسب الناتج عن توازي ${d}{e}$ و${b}{c}$: "
            f"$\\dfrac{{{a}{d}}}{{{d}{b}}}=\\dfrac{{{a}{e}}}{{{e}{c}}}$",
            method,
            finish,
        ),
        "A",
        {
            "type": "parallel_division",
            "values": {"AD": ad, "DB": db, "AE": ae, "EC": ec},
            "asked": unknown,
            "value": value,
        },
        wrong_kinds=kinds,
    )


@variant("3.5", G10, example=3)
def medial_triangle_perimeter(rng: random.Random) -> Problem:
    a, b, c = rng.choice([("A", "B", "C"), ("P", "Q", "R"), ("K", "L", "M")])
    d, e, f = {"A": ("D", "E", "F"), "P": ("S", "T", "U"), "K": ("N", "X", "Y")}[a]
    sides = rng.choice(
        [
            (8, 10, 12),
            (12, 14, 18),
            (10, 16, 18),
            (14, 18, 20),
            (16, 20, 24),
            (6, 8, 10),
            (20, 24, 28),
            (18, 22, 26),
        ]
    )
    perimeter = sum(sides) // 2
    wrong, kinds = tagged_lengths(
        perimeter,
        ("concept", sum(sides)),
        ("partial", sides[0] // 2 + sides[1] // 2),
        ("formula", sum(sides) // 4),
    )
    return Problem(
        "3.5",
        f"في المثلث ${a}{b}{c}$: ${a}{b}={sides[0]}$ سم و${b}{c}={sides[1]}$ سم و${c}{a}={sides[2]}$ سم. "
        f"النقاط ${d}$ و${e}$ و${f}$ منتصفات ${a}{b}$ و${b}{c}$ و${c}{a}$ على الترتيب. أوجد محيط المثلث ${d}{e}{f}$.",
        lengths(perimeter),
        wrong,
        (
            f"كل ضلع في المثلث ${d}{e}{f}$ يصل بين منتصفي ضلعين في المثلث الكبير، فطوله نصف طول الضلع الثالث.",
            f"${d}{e}=\\dfrac{{{sides[2]}}}{{2}}={sides[2] // 2}$ سم، و${e}{f}=\\dfrac{{{sides[0]}}}{{2}}={sides[0] // 2}$ سم، "
            f"و${f}{d}=\\dfrac{{{sides[1]}}}{{2}}={sides[1] // 2}$ سم.",
            f"المحيط $={sides[2] // 2}+{sides[0] // 2}+{sides[1] // 2}={perimeter}$ سم.",
        ),
        "A",
        {"type": "medial_perimeter", "sides": sides, "value": perimeter},
        wrong_kinds=kinds,
    )


@variant("3.5", G10, example=2)
def parallel_line_find_x(rng: random.Random) -> Problem:
    a, b, c, d, e = rng.choice(LETTER_SETS)
    while True:
        u, v = reduced_pair(rng, 2, 6)
        x0, unit_one, unit_two = rng.randint(2, 9), rng.randint(2, 4), rng.randint(1, 3)
        m1, m2 = rng.randint(1, 4), rng.randint(1, 4)
        db, ad0, ec, ae0 = v * unit_one, u * unit_one, v * unit_two, u * unit_two
        n1, n2 = ad0 - m1 * x0, ae0 - m2 * x0
        if m1 * ec != m2 * db and abs(n1) <= 12 and abs(n2) <= 12:
            break
    shown_ad, shown_ae = f"{lead(m1)}x{signed(n1)}", f"{lead(m2)}x{signed(n2)}"
    ad_expr, ae_expr = m1 * x + n1, m2 * x + n2
    whole = ad0 + db
    coefficient, constant = m1 * ec - m2 * db, n2 * db - n1 * ec
    return Problem(
        "3.5",
        f"في المثلث ${a}{b}{c}$ تقع ${d}$ على ${a}{b}$ و${e}$ على ${a}{c}$ بحيث ${d}{e}\\parallel {b}{c}$. "
        f"إذا كان ${a}{d}={shown_ad}$ سم و${d}{b}={db}$ سم و${a}{e}={shown_ae}$ سم و${e}{c}={ec}$ سم، "
        f"فأوجد قيمة $x$ ثم طول ${a}{b}$.",
        f"$x={x0}$ و${a}{b}={whole}$ سم",
        (
            f"$x={x0 + 1}$ و${a}{b}={whole + m1}$ سم",
            f"$x={x0 - 1}$ و${a}{b}={whole - m1}$ سم",
            f"$x={x0}$ و${a}{b}={ad0}$ سم",
        ),
        (
            f"توازي ${d}{e}$ و${b}{c}$ يعطي التناسب $\\dfrac{{{a}{d}}}{{{d}{b}}}=\\dfrac{{{a}{e}}}{{{e}{c}}}$، "
            f"أي $\\dfrac{{{shown_ad}}}{{{db}}}=\\dfrac{{{shown_ae}}}{{{ec}}}$",
            f"نضرب طرفًا في وسط: ${ec}({shown_ad})={db}({shown_ae})$، أي ${tex(sp.expand(ec * ad_expr))}={tex(sp.expand(db * ae_expr))}$",
            f"نجمع الحدود المتشابهة: ${coefficient}x={constant}$، إذن $x=\\dfrac{{{constant}}}{{{coefficient}}}={x0}$.",
            f"${a}{d}={m1}({x0}){signed(n1)}={ad0}$ سم، فـ${a}{b}={a}{d}+{d}{b}={ad0}+{db}={whole}$ سم.",
        ),
        "R",
        {"type": "parallel_algebra", "proportion": (ad_expr, db, ae_expr, ec), "x": x0, "total": whole},
        wrong_kinds=("nearby", "nearby", "partial"),
    )


TRANSVERSALS = (
    ("ثلاثة شوارع متوازية يقطعها شارعان", "الشارع الأول", "الشارع الثاني"),
    ("ثلاثة أسلاك متوازية يقطعها ساقان", "الساق الأولى", "الساق الثانية"),
    ("ثلاث قنوات ري متوازية يقطعها طريقان", "الطريق الأول", "الطريق الثاني"),
)


@variant("3.5", G10, example=3)
def parallel_lines_two_transversals(rng: random.Random) -> Problem:
    scene, first, second = rng.choice(TRANSVERSALS)
    u, v = reduced_pair(rng, 2, 8)
    s, t = rng.randint(1, 4), rng.randint(2, 6)
    if s == t:
        s += 1
    p, q = u * s, v * s
    one, two, total = u * t, v * t, (u + v) * t
    answer = f"${one}$ م و${two}$ م"
    wrong, kinds = tagged_wrongs(
        answer,
        ("swap", f"${two}$ م و${one}$ م"),
        ("formula", f"${total - p}$ م و${total - q}$ م"),
        ("nearby", f"${one + 1}$ م و${two - 1}$ م"),
        ("formula", f"${total // 2}$ م و${total - total // 2}$ م"),
        ("nearby", f"${one + 2}$ م و${two - 2}$ م"),
    )
    return Problem(
        "3.5",
        f"{scene}. على {first} تحدد المستقيمات المتوازية الثلاثة قطعتين طولاهما ${p}$ م و${q}$ م، "
        f"وعلى {second} المسافة بين المستقيمين الأول والثالث ${total}$ م. "
        f"أوجد طولي القطعتين اللتين تحددهما المستقيمات الثلاثة على {second}.",
        answer,
        wrong,
        (
            "المستقيمات المتوازية التي تقطع قاطعين تقسمهما إلى أجزاء متناسبة: النسبة بين القطعتين على أحد القاطعين تساوي "
            "النسبة بين القطعتين المناظرتين على الآخر.",
            f"نفرض القطعتين $a$ و$b$ حيث $a+b={total}$ و$\\dfrac{{a}}{{b}}=\\dfrac{{{p}}}{{{q}}}$",
            f"مجموع أجزاء النسبة ${p}+{q}={p + q}$، فـ$a=\\dfrac{{{p}}}{{{p + q}}}\\times {total}={one}$ م و$b={total}-{one}={two}$ م.",
        ),
        "R",
        {"type": "transversals", "first": (p, q), "second": (one, two), "total": total},
        wrong_kinds=kinds,
    )
