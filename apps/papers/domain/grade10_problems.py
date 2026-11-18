"""مولّدات العاشر، الفصل الأول (المقرر g10-s1): مسائل أصلية من مهارة الدرس بلغته، بلا نص من الكتاب.

كل صيغة تصرّح برقم مثال الكتاب الذي تقيس مهارته (example)، فيمنع اختبار النطاق بناء سؤال على مثال إثرائي.
البناء عكسي كما في generators.py: الرأس والمعاملات تُختار أولًا ثم تُشتق منها قاعدة الدالة بأعداد صحيحة.

الوحدة 1، الدوال التربيعية: 1.1 الدالة الرئيسة f(x)=ax²، 1.2 صيغة الرأس، 1.3 الصيغة القياسية.
الوحدة 2 (أ)، حل المعادلات التربيعية: 2.1 بالتمثيل البياني والجداول، 2.2 بالتحليل إلى العوامل، 2.3 المقادير
الجذرية، 2.5 إكمال المربع، 2.6 القانون العام والمميز.
الوحدة 2 (ب): 2.7 المعادلات النسبية، 2.8 الأنظمة الخطية-التربيعية، 2.9 المتباينات التربيعية، 2.10 معادلة
الدائرة.
"""

from __future__ import annotations

import math
import random
from typing import Any

import sympy as sp

from apps.curriculum.courses import GRADE10_SLUG

from .generators import Problem, frac, m, minus, nz, tex, variant, with_unit, wrongs, x, y

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
    return Problem(
        "1.1",
        f"صف اتجاه فتحة التمثيل البياني للدالة $f(x)={ax2(a)}$ واتساعه مقارنةً بالتمثيل البياني "
        "للدالة التربيعية الرئيسة $g(x)=x^2$.",
        answer,
        (describe(up, not narrow), describe(not up, narrow), describe(not up, not narrow)),
        (
            f"$a={tex(a)}$ {sign_word(a)}، فالقطع المكافئ يفتح إلى {opening(a)}.",
            f"$|a|={tex(abs(a))}$ {'أكبر' if narrow else 'أصغر'} من $1$، فالتمثيل البياني "
            f"{'أضيق' if narrow else 'أوسع'} من التمثيل البياني للدالة $g$.",
        ),
        "K",
        {"type": "parabola_shape", "f": a * x**2, "answer": answer},
    )


@variant("1.1", G10, example=2)
def parabola_through_point(rng: random.Random) -> Problem:
    p = rng.choice([-4, -3, -2, 2, 3, 4])
    halves = [HALF, -HALF, sp.Rational(3, 2), -sp.Rational(3, 2)] if p % 2 == 0 else []
    a = rng.choice([-4, -3, -2, -1, 1, 2, 3, 4, *halves])
    q = a * p * p
    return Problem(
        "1.1",
        f"يمرّ التمثيل البياني للدالة $f(x)=ax^2$ بالنقطة $({p},{tex(q)})$. أوجد قيمة $a$.",
        m(a),
        wrongs(a, a * p, q * p * p, -a, q - p * p),
        (
            f"نعوّض إحداثيي النقطة في قاعدة الدالة: ${tex(q)}=a({p})^2$",
            f"${tex(q)}={p * p}a$",
            f"$a={frac(q, p * p)}={tex(a)}$",
        ),
        "K",
        {"type": "value", "f": a * x**2, "at": p, "value": q},
    )


@variant("1.1", G10, example=1)
def parabola_monotone_interval(rng: random.Random) -> Problem:
    a = scale(rng)
    increasing = rng.random() < 0.5
    right = bool(a > 0) == increasing
    word = "متزايدة" if increasing else "متناقصة"
    answer, other = ("$x>0$", "$x<0$") if right else ("$x<0$", "$x>0$")
    return Problem(
        "1.1",
        f"حدّد الفترة التي تكون فيها الدالة $f(x)={ax2(a)}$ {word}.",
        answer,
        (other, "جميع الأعداد الحقيقية", f"$x>{tex(a)}$"),
        (
            f"$a={tex(a)}$ {sign_word(a)}، فالقطع المكافئ يفتح إلى {opening(a)}، ورأسه $(0,0)$.",
            f"الدالة {word} على {'يمين' if right else 'يسار'} محور التماثل $x=0$، أي عندما {answer}.",
        ),
        "K",
        {"type": "parabola_monotone", "f": a * x**2, "increasing": increasing, "answer": answer},
    )


@variant("1.1", G10, example=4)
def square_area_cost(rng: random.Random) -> Problem:
    work, place = rng.choice([("تبليط", "أرضية"), ("تعشيب", "حديقة"), ("رصف", "ساحة")])
    rate = 5 * rng.randint(3, 12)
    side = rng.randint(3, 10)
    cost = rate * side * side
    unit = "ريال"
    answer = with_unit(cost, unit)
    return Problem(
        "1.1",
        f"تُعطى تكلفة {work} {place} مربعة الشكل طول ضلعها $x$ من الأمتار بالريال بالدالة "
        f"$f(x)={rate}x^2$. أوجد تكلفة {work} {place} طول ضلعها ${side}$ أمتار.",
        answer,
        wrongs(answer, *[with_unit(v, unit) for v in (rate * side, 2 * rate * side, rate + side * side)]),
        (
            f"نعوّض $x={side}$: $f({side})={rate}({side})^2$",
            f"$f({side})={rate}\\times{side * side}={cost}$",
        ),
        "K",
        {"type": "value", "f": rate * x**2, "at": side, "value": cost},
    )


@variant("1.1", G10, example=5)
def parabola_average_rate(rng: random.Random) -> Problem:
    a = rng.choice([-4, -3, -2, -1, 1, 2, 3, 4])
    p = rng.randint(-4, 3)
    q = rng.choice([n for n in range(p + 1, p + 5) if n != -p])
    low, high = a * p * p, a * q * q
    value = a * (p + q)
    return Problem(
        "1.1",
        f"أوجد متوسط معدل التغيّر للدالة $f(x)={ax2(a)}$ في الفترة ${p} \\le x \\le {q}$.",
        m(value),
        wrongs(value, high - low, a * (q - p), sp.Rational(high + low, q - p)),
        (
            f"$f({p})={low}$ و$f({q})={high}$",
            f"${frac(f'f({q})-f({p})', minus(q, p))}={frac(high - low, q - p)}={value}$",
        ),
        "A",
        {"type": "average", "f": a * x**2, "a": p, "b": q, "value": value},
    )


# الدرس 1.2: الدوال التربيعية في صيغة الرأس f(x)=a(x-h)²+k
def vertex_text(h: int, k: int) -> str:
    return f"الرأس $({h},{k})$، ومحور التماثل $x={h}$"


def translation_text(h: int, k: int) -> str:
    return (
        f"إزاحة {units(abs(h))} إلى {RIGHT if h > 0 else LEFT}، و{units(abs(k))} إلى {UP if k > 0 else DOWN}"
    )


@variant("1.2", G10, example=3)
def vertex_and_axis_from_vertex_form(rng: random.Random) -> Problem:
    a = rng.choice([*INTEGER_SCALES, HALF, -HALF])
    h = nz(rng, -6, 6)
    k = rng.choice([n for n in range(-8, 9) if n not in (0, h, -h)])
    return Problem(
        "1.2",
        f"حدّد إحداثيي رأس القطع المكافئ ومعادلة محور التماثل للدالة $f(x)={vertex_form(a, h, k)}$.",
        vertex_text(h, k),
        (vertex_text(-h, k), vertex_text(h, -k), vertex_text(k, h)),
        (
            "الدالة مكتوبة في صيغة الرأس $f(x)=a(x-h)^2+k$، ورأس القطع المكافئ $(h,k)$.",
            f"بالمقارنة: $h={h}$ و$k={k}$، فالرأس $({h},{k})$.",
            f"محور التماثل هو المستقيم الرأسي المارّ بالرأس: $x={h}$.",
        ),
        "K",
        {"type": "vertex", "f": a * (x - h) ** 2 + k, "vertex": (h, k)},
    )


@variant("1.2", G10, example=3)
def translation_of_parent(rng: random.Random) -> Problem:
    h, k = nz(rng, -6, 6), nz(rng, -6, 6)
    answer = translation_text(h, k)
    return Problem(
        "1.2",
        f"صف كيف ينتج التمثيل البياني للدالة $g(x)={vertex_form(1, h, k)}$ من التمثيل البياني "
        "للدالة $f(x)=x^2$.",
        answer,
        (translation_text(-h, k), translation_text(h, -k), translation_text(-h, -k)),
        (
            f"$h={h}$: إزاحة أفقية {units(abs(h))} إلى {RIGHT if h > 0 else LEFT}.",
            f"$k={k}$: إزاحة رأسية {units(abs(k))} إلى {UP if k > 0 else DOWN}.",
        ),
        "K",
        {"type": "translation", "g": (x - h) ** 2 + k, "text": answer},
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
    return Problem(
        "1.2",
        stem,
        rule(h, k),
        (rule(-h, k), rule(h, -k), rule(-h, -k)),
        (
            f"الإزاحة الأفقية تعطي $h={h}$، والإزاحة الرأسية تعطي $k={k}$.",
            f"نعوّض في $g(x)=(x-h)^2+k$: $g(x)={vertex_form(1, h, k)}$",
        ),
        "K",
        {"type": "translation", "g": (x - h) ** 2 + k, "text": stem},
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
    return Problem(
        "1.2",
        f"رأس قطع مكافئ هو النقطة $({h},{k})$، ويمرّ القطع بالنقطة $({p},{q})$. "
        "اكتب قاعدة الدالة التربيعية التي تمثّله في صيغة الرأس.",
        answer,
        wrongs(answer, rule(a, -h, k), rule(-a, h, k), rule(a, k, h), rule(a, h, -k), rule(-a, -h, k)),
        (
            f"نعوّض الرأس في صيغة الرأس: $f(x)=a{shifted(h)}^2{signed(k)}$",
            f"نعوّض النقطة $({p},{q})$: ${q}=a({minus(p, h)})^2{signed(k)}$",
            f"إذن $a={q - k}$" if d * d == 1 else f"${q - k}={d * d}a$، إذن $a={tex(a)}$",
        ),
        "A",
        {"type": "vertex_point", "f": a * (x - h) ** 2 + k, "vertex": (h, k), "point": (p, q)},
    )


def ball_wrongs(answer: str, peak: int, at: int, start: int) -> tuple[str, ...]:
    """أخطاء شائعة في مسألة أقصى ارتفاع: ارتفاع البداية، وزمن العودة إليه، وتبديل الإحداثيين."""
    unit = "مترًا"
    return wrongs(
        answer,
        f"{with_unit(peak, unit)} عند $x={2 * at}$",
        f"{with_unit(10 * at, unit)} عند $x={at}$",
        f"{with_unit(peak + start, unit)} عند $x={at}$",
    )


@variant("1.2", G10, example=5)
def ball_height_vertex_form(rng: random.Random) -> Problem:
    at, start = rng.randint(2, 4), rng.randint(1, 9)
    peak = 5 * at * at + start
    answer = f"{with_unit(peak, 'مترًا')} عند $x={at}$"
    return Problem(
        "1.2",
        "قُذفت كرة إلى الأعلى، ويُعطى ارتفاعها بالأمتار بعد $x$ من الثواني بالدالة "
        f"$f(x)={vertex_form(-5, at, peak)}$. أوجد أقصى ارتفاع تبلغه الكرة والزمن الذي تبلغه عنده.",
        answer,
        ball_wrongs(answer, peak, at, start),
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
    )


# الدرس 1.3: الدوال التربيعية في الصيغة القياسية f(x)=ax²+bx+c
@variant("1.3", G10, example=2)
def axis_and_vertex_from_standard_form(rng: random.Random) -> Problem:
    a, h, k = rng.choice(INTEGER_SCALES), nz(rng, -4, 4), rng.randint(-9, 9)
    f, b, c = standard_from_vertex(a, h, k)

    def text(px: int) -> str:
        return f"محور التماثل $x={px}$، والرأس $({px},{a * px * px + b * px + c})$"

    answer = text(h)
    return Problem(
        "1.3",
        f"أوجد معادلة محور التماثل وإحداثيي رأس القطع المكافئ للدالة $f(x)={tex(f)}$.",
        answer,
        wrongs(answer, text(-h), text(2 * h), f"محور التماثل $x={h}$، والرأس $({h},{c})$", text(-2 * h)),
        (
            f"$a={a}$ و$b={b}$، فمحور التماثل {axis_step(a, b, h)}",
            f"الإحداثي $y$ للرأس: {value_step(a, b, c, h, k)}",
            f"الرأس $({h},{k})$.",
        ),
        "K",
        {"type": "vertex", "f": f, "vertex": (h, k)},
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
    return Problem(
        "1.3",
        f"حدّد المقطع $y$ للتمثيل البياني للدالة $f(x)={tex(f)}$ واتجاه فتحة القطع المكافئ.",
        answer,
        wrongs(answer, text(c, not up), text(b, up), text(a, not up), text(b, not up)),
        (
            f"المقطع $y$ هو قيمة الدالة عند $x=0$: $f(0)={c}$.",
            f"$a={a}$ {sign_word(a)}، فالقطع المكافئ يفتح إلى {opening(a)}.",
        ),
        "K",
        {"type": "standard_features", "f": f, "answer": answer},
    )


def extreme_text(is_max: bool, value: int) -> str:
    return f"قيمة {'عظمى' if is_max else 'صغرى'} تساوي ${value}$"


@variant("1.3", G10, example=3)
def extreme_value_from_standard_form(rng: random.Random) -> Problem:
    a, h, k = rng.choice(INTEGER_SCALES), nz(rng, -4, 4), rng.randint(-9, 9)
    f, b, c = standard_from_vertex(a, h, k)
    is_max = a < 0
    answer = extreme_text(is_max, k)
    return Problem(
        "1.3",
        f"هل للدالة $f(x)={tex(f)}$ قيمة عظمى أم قيمة صغرى؟ أوجد هذه القيمة.",
        answer,
        wrongs(
            answer,
            extreme_text(not is_max, k),
            extreme_text(is_max, c),
            extreme_text(not is_max, c),
            extreme_text(is_max, h),
        ),
        (
            f"$a={a}$ {sign_word(a)}، فالقطع المكافئ يفتح إلى {opening(a)}، وللدالة قيمة "
            f"{'عظمى' if is_max else 'صغرى'} عند الرأس.",
            f"محور التماثل {axis_step(a, b, h)}",
            value_step(a, b, c, h, k),
        ),
        "A",
        {"type": "parabola_extreme", "f": f, "at": h, "value": k, "answer": answer},
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
    return Problem(
        "1.3",
        f"الدالة $f(x)={tex(f)}$، والدالة $g$ دالة تربيعية يفتح تمثيلها البياني إلى الأسفل ورأسه "
        f"$({h_g},{top_g})$. أيّ الدالتين قيمتها العظمى أكبر؟ وما الفرق بين القيمتين العظميين؟",
        answer,
        wrongs(
            answer,
            text(smaller, gap),
            text(larger, top_f + top_g),
            text(smaller, top_f + top_g),
            text(larger, gap + 1),
        ),
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
    )


@variant("1.3", G10, example=2)
def ball_height_standard_form(rng: random.Random) -> Problem:
    at, start = rng.randint(2, 4), rng.randint(1, 9)
    peak = 5 * at * at + start
    f, b, c = standard_from_vertex(-5, at, peak)
    answer = f"{with_unit(peak, 'مترًا')} عند $x={at}$"
    return Problem(
        "1.3",
        "رُميت كرة إلى الأعلى، ويُعطى ارتفاعها بالأمتار بعد $x$ من الثواني بالدالة "
        f"$f(x)={tex(f)}$. أوجد أقصى ارتفاع تبلغه الكرة والزمن الذي تبلغه عنده.",
        answer,
        ball_wrongs(answer, peak, at, start),
        (
            f"$a=-5$ سالب، فللدالة قيمة عظمى عند الرأس، ومحور التماثل {axis_step(-5, b, at)}",
            value_step(-5, b, c, at, peak),
            f"أقصى ارتفاع ${peak}$ مترًا، وتبلغه الكرة عند $x={at}$.",
        ),
        "A",
        {"type": "optimum", "f": f, "low": 0, "high": 2 * at, "arg": at, "value": peak, "max": True},
    )


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


def solution_wrongs(answer: str, r1: Any, r2: Any) -> tuple[str, ...]:
    """أخطاء الإشارة أولًا ثم قيم قريبة؛ الثلاثة الأخيرة تختلف دائمًا عن الجواب وعن بعضها."""
    return wrongs(
        answer,
        solutions(-r1, -r2),
        solutions(-r1, r2),
        solutions(r1, -r2),
        solutions(r1 + 1, r2 + 1),
        solutions(r1 - 1, r2 - 1),
        solutions(r1, r2 + 1),
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
    return Problem(
        "2.1",
        f"يقطع التمثيل البياني للدالة $f(x)={tex(f)}$ المحور $x$ عند النقطتين $({r1},0)$ و$({r2},0)$. "
        f"ما حلول المعادلة ${tex(f)}=0$؟",
        answer,
        wrongs(
            answer,
            solutions(-r1, -r2),
            f"$x={f.subs(x, 0)}$",
            solutions(r1 + 1, r2 + 1),
            solutions(r1),
            solutions(r2),
        ),
        (
            "حلول المعادلة $f(x)=0$ هي أصفار الدالة $f$، أي الإحداثيات $x$ لنقاط تقاطع تمثيلها البياني "
            "مع المحور $x$.",
            f"المقطعان $x$ هما ${r1}$ و${r2}$، إذن {answer}.",
        ),
        "K",
        {"type": "roots", "f": f, "roots": (r1, r2)},
    )


@variant("2.1", G10, example=2)
def solutions_from_table(rng: random.Random) -> Problem:
    r1 = rng.randint(-4, 3)
    r2 = r1 + rng.randint(1, 4)
    f = sp.expand(rng.choice([1, -1]) * (x - r1) * (x - r2))
    low, high = r1 - 1, r2 + 1
    table = "، ".join(f"$f({px})={f.subs(x, px)}$" for px in range(low, high + 1))
    answer = solutions(r1, r2)
    return Problem(
        "2.1",
        f"أُنشئ جدول قيم للدالة $f(x)={tex(f)}$، فكانت: {table}. ما حلول المعادلة ${tex(f)}=0$؟",
        answer,
        wrongs(
            answer,
            solutions(low, high),
            solutions(r1),
            solutions(r2),
            solutions(-r1, -r2),
            f"$x={f.subs(x, 0)}$",
        ),
        (
            "حلول المعادلة هي قيم $x$ التي تكون عندها $f(x)=0$.",
            f"من الجدول: $f({r1})=0$ و$f({r2})=0$، إذن {answer}.",
        ),
        "K",
        {"type": "roots", "f": f, "roots": (r1, r2)},
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
    return Problem(
        "2.1",
        f"رأس القطع المكافئ الذي يمثّل الدالة التربيعية $f$ هو النقطة $({h},{k})$، ويفتح القطع إلى "
        f"{direction}. كم حلًّا حقيقيًّا للمعادلة $f(x)=0$؟",
        answer,
        wrongs(answer, *[text for n, text in COUNTS.items() if n != count], "عدد لا نهائي من الحلول"),
        (reason, f"إذن {COUNT_PHRASES[count]}."),
        "A",
        {"type": "solution_count", "f": (1 if up else -1) * (x - h) ** 2 + k, "count": count},
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
    )


@variant("2.1", G10, example=3)
def approximate_landing_time(rng: random.Random) -> Problem:
    f, v, s, _, low, high = projectile(rng)
    answer = seconds(high)
    return Problem(
        "2.1",
        "رُميت كرة إلى الأعلى، ويُعطى ارتفاعها بالأمتار بعد $x$ من الثواني بالدالة "
        f"$f(x)={tex(f)}$. يقطع التمثيل البياني للدالة المحور $x$ عند $x\\approx{tenth(low)}$ "
        f"و$x\\approx{tenth(high)}$. بعد كم ثانية تقريبًا تصل الكرة إلى الأرض؟",
        answer,
        wrongs(answer, seconds(-low), seconds(high - low), seconds(v / 10), seconds(s), seconds(high / 2)),
        (
            "تصل الكرة إلى الأرض عندما يكون ارتفاعها صفرًا، أي عند حل موجب للمعادلة $f(x)=0$.",
            f"الحل $x\\approx{tenth(low)}$ سالب فلا يمثّل زمنًا، إذن تصل الكرة إلى الأرض بعد "
            f"${tenth(high)}$ ثانية تقريبًا.",
        ),
        "K",
        {"type": "approx_root", "f": f, "value": float(tenth(high))},
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
    return Problem(
        "2.2",
        f"حلّ المعادلة ${left}=0$ باستعمال خاصية ناتج الضرب الصفري.",
        answer,
        solution_wrongs(answer, r1, r2),
        (f"بخاصية ناتج الضرب الصفري: ${factors[0]}=0$ أو ${factors[1]}=0$", f"إذن {answer}."),
        "K",
        {"type": "roots", "f": sp.expand((x - r1) * (x - r2)), "roots": (r1, r2)},
    )


@variant("2.2", G10, example=2)
def solve_trinomial_by_factoring(rng: random.Random) -> Problem:
    while True:
        r1, r2 = two_roots(rng, -9, 9, zero=False)
        if r1 + r2:
            break
    f = sp.expand((x - r1) * (x - r2))
    answer = solutions(r1, r2)
    return Problem(
        "2.2",
        f"حلّ المعادلة ${tex(f)}=0$ بالتحليل إلى العوامل.",
        answer,
        solution_wrongs(answer, r1, r2),
        (
            f"نحلّل ثلاثية الحدود: ${product(r1, r2)}=0$",
            f"بخاصية ناتج الضرب الصفري: ${linear(r1)}=0$ أو ${linear(r2)}=0$",
            f"إذن {answer}.",
        ),
        "K",
        {"type": "roots", "f": f, "roots": (r1, r2)},
    )


@variant("2.2", G10, example=2)
def solve_rearranged_equation_by_factoring(rng: random.Random) -> Problem:
    p, r = rng.choice([2, 3]), nz(rng, -6, 6)
    q = rng.choice([n for n in range(-7, 8) if n and math.gcd(p, abs(n)) == 1])
    other = sp.Rational(-q, p)
    f = sp.expand((p * x + q) * (x - r))
    answer = solutions(other, r)
    return Problem(
        "2.2",
        f"حلّ المعادلة ${tex(f + q * r)}={q * r}$ بالتحليل إلى العوامل.",
        answer,
        solution_wrongs(answer, other, r),
        (
            f"نكتب المعادلة في الصيغة القياسية: ${tex(f)}=0$",
            f"نحلّل ثلاثية الحدود: $({p}x{q:+d}){shifted(r)}=0$",
            f"بخاصية ناتج الضرب الصفري: ${p}x{q:+d}=0$ أو ${linear(r)}=0$",
            f"إذن {answer}.",
        ),
        "A",
        {"type": "roots", "f": f, "roots": (other, r)},
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
    return Problem(
        "2.2",
        f"أوجد المقطعين $x$ ومعادلة محور التماثل للتمثيل البياني للدالة $f(x)={lead(a)}{product(p, q)}$.",
        answer,
        wrongs(
            answer,
            text(-q, -p, -h),
            text(p, q, p + q),
            text(p, q, q - p),
            text(p - 1, q - 1, h - 1),
            text(p, q, h + 1),
            text(p, q, h - 1),
        ),
        (
            f"المقطعان $x$ هما صفرا الدالة: $x={p}$ و$x={q}$.",
            f"محور التماثل يمرّ بمنتصف المسافة بين المقطعين: $x=\\dfrac{{{plus(p, q)}}}{{2}}={h}$",
        ),
        "K",
        {"type": "factored_axis", "f": sp.expand(a * (x - p) * (x - q)), "roots": (p, q), "axis": h},
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
    return Problem(
        "2.2",
        f"يقطع قطع مكافئ المحور $x$ عند $x={p}$ و$x={q}$، ويمرّ بالنقطة $({s},{t})$. "
        "اكتب قاعدة الدالة التربيعية التي تمثّله في الصيغة التحليلية.",
        answer,
        wrongs(
            answer,
            rule(a, -p, -q),
            rule(-a, p, q),
            rule(1, p, q),
            rule(-a, -p, -q),
            rule(2 * a, p, q),
            rule(3 * a, p, q),
        ),
        (
            f"المقطعان $x$ هما ${p}$ و${q}$، فالصيغة التحليلية $f(x)=a{product(p, q)}$",
            f"نعوّض النقطة $({s},{t})$: ${t}=a({minus(s, p)})({minus(s, q)})$",
            f"${t}={(s - p) * (s - q)}a$، إذن $a={a}$",
        ),
        "A",
        {"type": "factored_point", "f": sp.expand(a * (x - p) * (x - q)), "roots": (p, q), "point": (s, t)},
    )


# الدرس 2.3: إعادة كتابة المقادير الجذرية
@variant("2.3", G10, example=1)
def simplify_square_root(rng: random.Random) -> Problem:
    k, free = rng.randint(2, 9), rng.choice(SQUARE_FREE)
    n = k * k * free
    return Problem(
        "2.3",
        f"اكتب $\\sqrt{{{n}}}$ في أبسط صورة.",
        m(root(k, free)),
        wrongs(
            m(root(k, free)),
            m(root(k * k, free)),
            m(root(free, k)),
            m(root(k, k * free)),
            m(root(k + 1, free)),
        ),
        (
            f"أكبر عامل مربع كامل للعدد ${n}$ هو ${k * k}$: $\\sqrt{{{n}}}=\\sqrt{{{k * k}\\cdot{free}}}$",
            f"$\\sqrt{{{k * k}}}\\cdot\\sqrt{{{free}}}={root(k, free)}$",
        ),
        "K",
        {"type": "radical", "square": sp.Integer(n), "coefficient": sp.Integer(k), "radicand": free},
    )


@variant("2.3", G10, example=2)
def simplify_multiple_of_square_root(rng: random.Random) -> Problem:
    c, k, free = rng.randint(2, 6), rng.randint(2, 5), rng.choice(SQUARE_FREE)
    n = k * k * free
    answer = m(root(c * k, free))
    return Problem(
        "2.3",
        f"اكتب ${root(c, n)}$ في أبسط صورة.",
        answer,
        wrongs(
            answer,
            m(root(c + k, free)),
            m(root(c * k * k, free)),
            m(root(c, free)),
            m(root(c * k + 1, free)),
        ),
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
    return Problem(
        "2.3",
        f"اكتب $\\sqrt{{{n}x^{{{p}}}}}$ في أبسط صورة، حيث $x\\geq 0$.",
        answer,
        (text(k, half, 1 - odd), text(k * k, half, odd), text(k, p, odd)),
        (
            "نكتب المجذور بدلالة عوامل مربعة كاملة: "
            f"$\\sqrt{{{n}x^{{{p}}}}}=\\sqrt{{{k * k}\\cdot {even}\\cdot {free}{'x' if odd else ''}}}$",
            f"$\\sqrt{{{k * k}}}\\cdot\\sqrt{{{even}}}\\cdot\\sqrt{{{free}{'x' if odd else ''}}}="
            f"{answer[1:-1]}$",
        ),
        "A",
        {"type": "radical", "square": n * x**p, "coefficient": k * x**half, "radicand": free * x**odd},
    )


@variant("2.3", G10, example=4)
def multiply_radical_expressions(rng: random.Random) -> Problem:
    g = rng.choice([2, 3, 5])
    u, v = rng.sample([n for n in (1, 2, 3, 5, 7) if n != g], 2)
    a, b = rng.randint(1, 5), rng.randint(1, 5)
    first, second, outer = g * u, g * v, a * b
    answer = m(root(outer * g, u * v))
    split = f"{g * g}\\cdot{u * v}"
    return Problem(
        "2.3",
        f"أوجد ناتج الضرب في أبسط صورة: ${root(a, first)}\\cdot{root(b, second)}$",
        answer,
        wrongs(
            answer,
            m(root(outer, u * v)),
            m(root(outer * g * g, u * v)),
            m(root((a + b) * g, u * v)),
            m(root(outer * g, u * v * g)),
        ),
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
    )


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
    return Problem(
        "2.3",
        f"{thing} مستطيلة الشكل طولها ${length}$ وعرضها ${width}$ {unit}. اكتب طول قطرها في أبسط صورة جذرية.",
        answer,
        wrongs(answer, m(width + length), m(root(k * k, free)), m(root(k + 1, free)), m(root(k, free + 1))),
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
    return Problem(
        "2.5",
        f"أوجد قيمة $c$ التي تجعل $x^2{b:+d}x+c$ ثلاثية حدود في صورة مربع كامل.",
        m(c),
        wrongs(c, sp.Rational(b, 2), sp.Integer(b * b), sp.Rational(b * b, 2), sp.Integer(2 * b)),
        (
            f"نضيف مربع نصف معامل $x$: $c=\\left(\\dfrac{{{b}}}{{2}}\\right)^2={tex(c)}$",
            f"ثلاثية الحدود $x^2{b:+d}x+{tex(c)}$ تساوي ${binomial(b)}^2$.",
        ),
        "K",
        {"type": "perfect_square", "b": b, "c": c},
    )


@variant("2.5", G10, example=1)
def perfect_square_trinomial_as_binomial_square(rng: random.Random) -> Problem:
    h = nz(rng, -10, 10)
    b, c = 2 * h, h * h
    answer = f"${binomial(b)}^2$"
    return Problem(
        "2.5",
        f"اكتب ثلاثية الحدود $x^2{b:+d}x+{c}$ في صورة مربع ثنائية حد.",
        answer,
        wrongs(
            answer,
            f"$(x{-h:+d})^2$",
            f"$(x{b:+d})^2$",
            f"$(x{h:+d})(x{-h:+d})$",
            f"$(x{c:+d})^2$",
        ),
        (
            f"نصف معامل $x$ هو ${h}$، ومربعه ${c}$ يساوي الحد الثابت.",
            f"إذن $x^2{b:+d}x+{c}={binomial(b)}^2$.",
        ),
        "K",
        {"type": "perfect_square", "b": b, "c": c},
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
    return Problem(
        "2.5",
        f"حلّ المعادلة ${tex(f)}=0$ بإكمال المربع.",
        answer,
        (
            surd_solutions(-h, d),
            f"$x={h}\\pm{d}$",
            surd_solutions(h, d + h * h),
        ),
        completing_steps(h, d),
        "A",
        {"type": "roots", "f": f, "roots": (h + sp.sqrt(d), h - sp.sqrt(d))},
    )


@variant("2.5", G10, example=3)
def solve_by_completing_the_square_with_leading_coefficient(rng: random.Random) -> Problem:
    a, h, d = rng.choice([2, 3, 4, 5]), nz(rng, -5, 5), rng.choice(SQUARE_FREE)
    monic = sp.expand((x - h) ** 2 - d)
    f = sp.expand(a * monic)
    answer = surd_solutions(h, d)
    return Problem(
        "2.5",
        f"حلّ المعادلة ${tex(f)}=0$ بإكمال المربع.",
        answer,
        (
            surd_solutions(-h, d),
            surd_solutions(h, a * d),
            f"$x={h}\\pm{d}$",
        ),
        (f"نقسم الطرفين على ${a}$: ${tex(monic)}=0$", *completing_steps(h, d)),
        "A",
        {"type": "roots", "f": f, "roots": (h + sp.sqrt(d), h - sp.sqrt(d))},
    )


@variant("2.5", G10, example=4)
def vertex_form_by_completing_the_square(rng: random.Random) -> Problem:
    h, k = nz(rng, -6, 6), nz(rng, -9, 9)
    b, c = -2 * h, h * h + k
    f = x**2 + b * x + c

    def text(dh: int, dk: int, vertex: tuple[int, int]) -> str:
        return f"$f(x)={vertex_form(1, dh, dk)}$، والرأس $({vertex[0]},{vertex[1]})$"

    answer = text(h, k, (h, k))
    return Problem(
        "2.5",
        f"اكتب الدالة $f(x)={tex(f)}$ في صيغة الرأس بإكمال المربع، ثم حدّد رأس القطع المكافئ.",
        answer,
        wrongs(
            answer,
            text(-h, k, (-h, k)),
            text(h, k, (-h, k)),
            text(h, c, (h, c)),
            text(h, -k, (h, -k)),
        ),
        (
            f"نضيف مربع نصف معامل $x$ ونطرحه: $f(x)=(x^2{b:+d}x+{h * h})-{h * h}{signed(c)}$",
            f"$f(x)={vertex_form(1, h, k)}$",
            f"الرأس $({h},{k})$.",
        ),
        "A",
        {"type": "vertex", "f": f, "vertex": (h, k)},
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
    return Problem(
        "2.6",
        f"حلّ المعادلة ${tex(f)}=0$ باستعمال القانون العام.",
        answer,
        solution_wrongs(answer, other, r),
        (
            *formula_values(a, b, c, disc),
            f"$x=\\dfrac{{-b\\pm\\sqrt{{b^2-4ac}}}}{{2a}}=\\dfrac{{{-b}\\pm{abs(q + a * r)}}}{{{2 * a}}}$",
            f"إذن {answer}.",
        ),
        "K",
        {"type": "roots", "f": f, "roots": (other, r)},
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
    return Problem(
        "2.6",
        f"حلّ المعادلة ${tex(f)}=0$ باستعمال القانون العام.",
        answer,
        (text(b, surd, 2 * a), text(-b, surd, a if a > 1 else 4), text(-b, str(disc), 2 * a)),
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
    return Problem(
        "2.6",
        f"أوجد قيمة المميز للمعادلة ${tex(a * x**2 + b * x + c)}=0$، ثم حدّد عدد حلولها الحقيقية.",
        answer,
        (text(disc, (count + 1) % 3), text(disc, (count + 2) % 3), text(slip, count_from(slip))),
        (
            *formula_values(a, b, c, disc),
            f"المميز {('سالب', 'يساوي صفرًا', 'موجب')[count]}، إذن {COUNT_PHRASES[count]}.",
        ),
        "K",
        {"type": "solution_count", "f": a * x**2 + b * x + c, "count": count, "discriminant": disc},
    )


@variant("2.6", G10, example=4)
def constant_for_one_real_solution(rng: random.Random) -> Problem:
    a, b = rng.choice([1, 2, 3, 4]), 2 * nz(rng, -6, 6)
    k = sp.Rational(b * b, 4 * a)
    reduced = f"={tex(k)}" if math.gcd(b * b, 4 * a) > 1 else ""
    return Problem(
        "2.6",
        f"أوجد قيمة $k$ التي تجعل للمعادلة ${lead(a)}x^2{b:+d}x+k=0$ حلًّا حقيقيًّا واحدًا.",
        m(k),
        wrongs(k, sp.Rational(b * b, a), sp.Rational(b * b, 2 * a), sp.Rational(b, 2 * a), -k),
        (
            "للمعادلة حل حقيقي واحد عندما يساوي المميز صفرًا: $b^2-4ac=0$",
            f"$({b})^2-4({a})k=0$",
            f"${b * b}-{4 * a}k=0$، إذن $k={frac(b * b, 4 * a)}{reduced}$",
        ),
        "A",
        {"type": "solution_count", "f": a * x**2 + b * x + k, "count": 1},
    )


@variant("2.6", G10, example=3)
def landing_time_by_quadratic_formula(rng: random.Random) -> Problem:
    f, v, s, disc, low, high = projectile(rng)
    answer = seconds(high)
    return Problem(
        "2.6",
        "قُذف جسم إلى الأعلى، ويُعطى ارتفاعه بالأمتار بعد $x$ من الثواني بالدالة "
        f"$f(x)={tex(f)}$. استعمل القانون العام لإيجاد الزمن الذي يصل عنده الجسم إلى الأرض، "
        "مقرّبًا الناتج إلى أقرب جزء من عشرة.",
        answer,
        wrongs(answer, seconds(-low), seconds(2 * high), seconds(v / 10), seconds(s), seconds(high - low)),
        (
            f"يصل الجسم إلى الأرض عندما $f(x)=0$، أي ${tex(f)}=0$",
            *formula_values(-5, v, s, disc),
            f"$x=\\dfrac{{{-v}\\pm\\sqrt{{{disc}}}}}{{-10}}$، أي $x\\approx{tenth(low)}$ أو "
            f"$x\\approx{tenth(high)}$",
            f"الزمن لا يكون سالبًا، إذن يصل الجسم إلى الأرض بعد ${tenth(high)}$ ثانية تقريبًا.",
        ),
        "A",
        {"type": "approx_root", "f": f, "value": float(tenth(high))},
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


def point_wrongs(answer: str, first: tuple[int, int], second: tuple[int, int]) -> tuple[str, ...]:
    """تبديل الإحداثيات وأخطاء الإشارة أولًا؛ البديلان الأخيران يخالفان الجواب وبعضهما دائمًا."""
    (x1, y1), (x2, y2) = first, second
    return wrongs(
        answer,
        points((x1, y2), (x2, y1)),
        points((y1, x1), (y2, x2)),
        points((x1, -y1), (x2, -y2)),
        points((-x1, y1), (-x2, y2)),
        points((x1 + 1, y1), (x2 + 1, y2)),
        points((x1, y1 + 1), (x2, y2 + 1)),
    )


# الدرس 2.7: حل المعادلات النسبية. المثالان 4 و5 إثرائيان: لا صيغة جوابها «لا حل»، ولا مسألة معدّل سرعة.
@variant("2.7", G10, example=1)
def rational_equation_with_constant_numerator(rng: random.Random) -> Problem:
    a, b = nz(rng, -9, 9), nz(rng, -9, 9)
    c = rng.choice([n for n in range(-6, 7) if n not in (0, 1)])
    value = sp.Rational(a, c) - b
    answer = solutions(value)
    return Problem(
        "2.7",
        f"حلّ المعادلة النسبية ${frac(a, linear(-b))}={c}$.",
        answer,
        wrongs(
            answer,
            solutions(sp.Rational(a, c) + b),
            solutions(-value),
            solutions(a * c - b),
            solutions(sp.Rational(c, a) - b),
            solutions(value + 1),
            solutions(value - 1),
        ),
        (
            f"نضرب طرفي المعادلة في المقام ${linear(-b)}$: ${a}={lead(c)}{shifted(-b)}$",
            f"${a}={lead(c)}x{c * b:+d}$",
            f"${lead(c)}x={a - c * b}$، إذن $x={tex(value)}$",
            f"القيمة لا تجعل المقام صفرًا، إذن حل المعادلة {answer}.",
        ),
        "K",
        {"type": "rational_equation", "lhs": a / (x + b), "rhs": sp.Integer(c), "solutions": (value,)},
    )


@variant("2.7", G10, example=1)
def rational_equation_as_proportion(rng: random.Random) -> Problem:
    a, c = rng.sample(range(1, 10), 2)
    b, d = rng.sample(range(-8, 9), 2)
    value = sp.Rational(c * b - a * d, a - c)
    answer = solutions(value)
    return Problem(
        "2.7",
        f"حلّ المعادلة النسبية ${frac(a, linear(-b))}={frac(c, linear(-d))}$.",
        answer,
        wrongs(
            answer,
            solutions(-value),
            solutions(sp.Rational(c * b + a * d, a - c)),
            solutions(sp.Rational(c * b - a * d, a + c)),
            solutions(sp.Rational(a * b - c * d, a - c)),
            solutions(value + 1),
            solutions(value - 1),
            solutions(value + 2),
        ),
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
    return Problem(
        "2.7",
        f"أيّ قيم $x$ لا يمكن أن تكون حلًّا للمعادلة ${text}$ لأنها تجعل مقامًا فيها يساوي صفرًا؟",
        answer,
        wrongs(
            answer,
            both(-high, -low),
            f"$x={low}$ فقط",
            f"$x={high}$ فقط",
            both(low + high, low * high),
        ),
        (
            f"المقام ${linear(p)}$ يساوي صفرًا عند $x={p}$، والمقام ${linear(q)}$ يساوي صفرًا عند $x={q}$.",
            f"${tex(bottom)}={product(low, high)}$، فيساوي صفرًا عند القيمتين نفسيهما.",
            f"إذن {answer} لا يمكن أن يكونا حلّين للمعادلة، وأي حل يساوي أحدهما حل غير مقبول.",
        ),
        "K",
        {"type": "excluded_values", "lhs": lhs, "rhs": rhs, "values": (p, q)},
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
    return Problem(
        "2.7",
        f"{together} في {hours(t)} عندما تعملان معًا. سرعة {first} في العمل تساوي {RATIOS[k]} سرعة "
        f"{second}. ما المدة التي تحتاج إليها {first if wanted_fast else second} {task} إذا عملت بمفردها؟",
        answer,
        wrongs(
            answer,
            hours(slow if wanted_fast else fast),
            hours(k * t),
            hours(2 * t),
            hours(slow + fast),
            hours(wanted + 1),
            hours(wanted + 2),
        ),
        (
            f"ليكن $x$ عدد الساعات التي تحتاج إليها {second} بمفردها، فمعدل عملها $\\dfrac{{1}}{{x}}$ من "
            f"العمل في الساعة، ومعدل عمل {first} $\\dfrac{{{k}}}{{x}}$.",
            f"معدل عملهما معًا $\\dfrac{{1}}{{{t}}}$: $\\dfrac{{1}}{{x}}+\\dfrac{{{k}}}{{x}}=\\dfrac{{1}}{{{t}}}$",
            f"نضرب الطرفين في ${t}x$: ${t}+{k * t}=x$، إذن $x={slow}$",
            last,
        ),
        "A",
        {"type": "work_rate", "times": (slow, fast), "together": t, "ratio": k, "answer": wanted},
    )


@variant("2.7", G10, example=2)
def work_rate_with_one_time_known(rng: random.Random) -> Problem:
    _, noun, task = rng.choice(JOBS)
    known, other = rng.sample(rng.choice(WORK_PAIRS), 2)
    t = known * other // (known + other)
    first, second = f"{noun} الأولى", f"{noun} الثانية"
    answer = hours(other)
    return Problem(
        "2.7",
        f"تحتاج {first} إلى {hours(known)} {task} إذا عملت بمفردها، وإذا عملت معها {second} أنجزتا "
        f"العمل في {hours(t)}. ما المدة التي تحتاج إليها {second} {task} إذا عملت بمفردها؟",
        answer,
        wrongs(
            answer,
            hours(known - t),
            hours(known + t),
            hours(2 * t),
            hours(other + 1),
            hours(other + 2),
            hours(other + 3),
        ),
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
    return Problem(
        "2.7",
        f"ما حل المعادلة ${text}$؟",
        answer,
        wrongs(
            answer,
            solutions(bad),
            solutions(good, bad),
            solutions(-good),
            solutions(-good, -bad),
            solutions(good + 1),
            solutions(good - 1),
        ),
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
    return Problem(
        "2.8",
        f"ما عدد حلول النظام الخطي-التربيعي $y={tex(parabola)}$ و$y={tex(line)}$؟",
        answer,
        wrongs(
            answer,
            *[text for n, text in SYSTEM_COUNTS.items() if n != count],
            "للنظام عدد لا نهائي من الحلول",
        ),
        (
            f"نساوي المقدارين: ${tex(parabola)}={tex(line)}$، أي ${tex(difference)}=0$",
            *formula_values(1, b, c, b * b - 4 * c),
            f"المميز {('سالب', 'يساوي صفرًا', 'موجب')[count]}، فالمستقيم والقطع المكافئ "
            f"{CROSSINGS[count]}، إذن {answer}.",
        ),
        "K",
        {"type": "system", "equations": (y - parabola, y - line), "count": count},
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
    return Problem(
        "2.8",
        f"يتقاطع التمثيلان البيانيان للمعادلتين $y={tex(parabola)}$ و$y={tex(line)}$ في نقطتين "
        f"إحداثياهما $x$ هما ${first[0]}$ و${second[0]}$. ما حلول النظام المكوّن من المعادلتين؟",
        answer,
        point_wrongs(answer, first, second),
        (
            "حلول النظام الخطي-التربيعي هي نقاط تقاطع المستقيم مع القطع المكافئ.",
            back_substitution(slope, d, first[0], second[0]),
            f"إذن حلّا النظام {answer}.",
        ),
        "K",
        {"type": "system", "equations": (y - parabola, y - line), "solutions": (first, second)},
    )


@variant("2.8", G10, example=3)
def solve_system_by_elimination(rng: random.Random) -> Problem:
    parabola, line, difference, slope, d, first, second = crossing_system(rng, 1)
    answer = points(first, second)
    return Problem(
        "2.8",
        f"حلّ النظام الخطي-التربيعي $y={tex(parabola)}$ و$y={tex(line)}$ بطريقة الحذف.",
        answer,
        point_wrongs(answer, first, second),
        (
            f"نطرح المعادلة الخطية من المعادلة التربيعية لحذف $y$: $0={tex(difference)}$",
            f"نحلّل إلى العوامل: ${product(first[0], second[0])}=0$، إذن {solutions(first[0], second[0])}",
            back_substitution(slope, d, first[0], second[0]),
            f"إذن حلّا النظام {answer}.",
        ),
        "A",
        {"type": "system", "equations": (y - parabola, y - line), "solutions": (first, second)},
    )


@variant("2.8", G10, example=4)
def solve_system_by_substitution(rng: random.Random) -> Problem:
    leading = rng.choice([-3, -2, -1, 2, 3])
    parabola, line, difference, slope, d, first, second = crossing_system(rng, leading)
    monic = sp.expand(difference / leading)
    answer = points(first, second)
    return Problem(
        "2.8",
        f"حلّ النظام الخطي-التربيعي $y={tex(line)}$ و$y={tex(parabola)}$ بطريقة التعويض.",
        answer,
        point_wrongs(answer, first, second),
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
    return Problem(
        "2.8",
        "قُذفت كرة إلى الأعلى من سطح مبنى، ويُعطى ارتفاعها بالأمتار بعد $x$ من الثواني بالدالة "
        f"$y={tex(ball)}$. في اللحظة نفسها بدأت طائرة مسيّرة بالصعود، ويُعطى ارتفاعها بالدالة "
        f"$y={tex(drone)}$. بعد كم ثانية يكون للكرة والطائرة الارتفاع نفسه؟ وما ذلك الارتفاع؟",
        answer,
        wrongs(
            answer,
            text(at, d + n * at),
            *[text(at + step, slope * (at + step) + d) for step in (1, 2, 3)],
        ),
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
    )


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
    return Problem(
        "2.10",
        f"اكتب معادلة الدائرة التي مركزها $({h},{k})$ وطول نصف قطرها ${shown}$.",
        answer,
        wrongs(
            answer,
            circle(-h, -k, r2),
            circle(h, k, slip),
            circle(-h, -k, slip),
            circle(k, h, r2),
            circle(h, k, 2 * r2),
            circle(h, k, r2 + 1),
            circle(h, k, 3 * r2),
        ),
        (
            f"$h={h}$، $k={k}$، $r={shown}$",
            "الصيغة القياسية لمعادلة الدائرة: $(x-h)^2+(y-k)^2=r^2$",
            f"نعوّض ونبسّط: $r^2={r2}$، إذن معادلة الدائرة {answer}.",
        ),
        "K",
        circle_check(h, k, r2),
    )


@variant("2.10", G10, example=2)
def center_and_radius_from_circle_equation(rng: random.Random) -> Problem:
    h, k = rng.randint(-7, 7), nz(rng, -7, 7)
    shown, r2, _ = radius(rng)

    def text(a: int, b: int, length: str) -> str:
        return f"المركز $({a},{b})$، وطول نصف القطر ${length}$"

    answer = text(h, k, shown)
    return Problem(
        "2.10",
        f"أوجد مركز الدائرة {circle(h, k, r2)} وطول نصف قطرها.",
        answer,
        wrongs(
            answer,
            text(-h, -k, shown),
            text(h, k, str(r2)),
            text(-h, -k, str(r2)),
            text(k, h, shown),
        ),
        (
            "الصيغة القياسية لمعادلة الدائرة: $(x-h)^2+(y-k)^2=r^2$",
            f"نكتب المعادلة بهذه الصيغة: $(x-({h}))^2+(y-({k}))^2=({shown})^2$",
            f"إذن $h={h}$، $k={k}$، $r={shown}$: {answer}.",
        ),
        "K",
        circle_check(h, k, r2),
    )


@variant("2.10", G10, example=1)
def circle_equation_from_center_and_point(rng: random.Random) -> Problem:
    h, k = rng.randint(-6, 6), rng.randint(-6, 6)
    dx, dy = nz(rng, -6, 6), nz(rng, -6, 6)
    p, q, r2 = h + dx, k + dy, dx * dx + dy * dy
    answer = circle(h, k, r2)
    return Problem(
        "2.10",
        f"اكتب معادلة الدائرة التي مركزها $({h},{k})$ وتمرّ بالنقطة $({p},{q})$.",
        answer,
        wrongs(
            answer,
            circle(p, q, r2),
            circle(-h, -k, r2),
            circle(h, k, abs(dx) + abs(dy)),
            circle(h, k, 2 * r2),
            circle(h, k, r2 + 1),
        ),
        (
            "طول نصف القطر هو المسافة بين المركز والنقطة، ونجد مربعه بنظرية فيثاغورس: "
            f"$r^2=({minus(p, h)})^2+({minus(q, k)})^2={dx * dx}+{dy * dy}={r2}$",
            f"نعوّض $h={h}$ و$k={k}$ و$r^2={r2}$ في الصيغة القياسية $(x-h)^2+(y-k)^2=r^2$.",
            f"إذن معادلة الدائرة {answer}.",
        ),
        "A",
        circle_check(h, k, r2, points=((p, q),)),
    )


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
    return Problem(
        "2.10",
        f"على مخطط إحداثي لحديقة عامة، تقع نهايتا قطر {place} عند النقطتين $({x1},{y1})$ و$({x2},{y2})$. "
        f"اكتب معادلة الدائرة التي تمثّل {edge}.",
        answer,
        wrongs(
            answer,
            circle(h, k, 4 * r2),
            circle(x2, y2, r2),
            circle(-h, -k, r2),
            circle(h, k, 2 * r2),
            circle(h, k, r2 + 1),
        ),
        (
            "مركز الدائرة نقطة منتصف القطر: "
            f"$\\left(\\dfrac{{{plus(x1, x2)}}}{{2}},\\dfrac{{{plus(y1, y2)}}}{{2}}\\right)=({h},{k})$",
            "مربع طول نصف القطر مربع المسافة بين المركز وإحدى نهايتي القطر: "
            f"$r^2=({minus(x2, h)})^2+({minus(y2, k)})^2={r2}$",
            f"إذن معادلة الدائرة {answer}.",
        ),
        "A",
        circle_check(h, k, r2, points=((x1, y1), (x2, y2)), diameter=True),
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
    return Problem(
        "2.10",
        f"حدّد موقع النقطة $({p},{q})$ بالنسبة إلى الدائرة {circle(h, k, r2)}: هل تقع على الدائرة أم "
        "داخلها أم خارجها؟",
        answer,
        (*[text for name, text in POSITIONS.items() if name != position], "هي مركز الدائرة"),
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
    )


@variant("2.10", G10, example=5)
def solve_line_and_circle_system(rng: random.Random) -> Problem:
    r2, slope, c, first, second = rng.choice(LINE_CIRCLE_SYSTEMS)
    line = slope * x + c
    answer = points(first, second)
    return Problem(
        "2.10",
        f"حلّ النظام الخطي-التربيعي $y={tex(line)}$ و$x^2+y^2={r2}$.",
        answer,
        point_wrongs(answer, first, second),
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
    )
