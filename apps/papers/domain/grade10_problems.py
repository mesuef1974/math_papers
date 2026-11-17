"""مولّدات العاشر، الفصل الأول (المقرر g10-s1): مسائل أصلية من مهارة الدرس بلغته، بلا نص من الكتاب.

كل صيغة تصرّح برقم مثال الكتاب الذي تقيس مهارته (example)، فيمنع اختبار النطاق بناء سؤال على مثال إثرائي.
البناء عكسي كما في generators.py: الرأس والمعاملات تُختار أولًا ثم تُشتق منها قاعدة الدالة بأعداد صحيحة.

الوحدة 1، الدوال التربيعية: 1.1 الدالة الرئيسة f(x)=ax²، 1.2 صيغة الرأس، 1.3 الصيغة القياسية.
"""

from __future__ import annotations

import random
from typing import Any

import sympy as sp

from apps.curriculum.courses import GRADE10_SLUG

from .generators import Problem, frac, m, minus, nz, tex, variant, with_unit, wrongs, x

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
        return f"يفتح إلى {UP if up else DOWN}، وهو {'أضيق' if narrow else 'أوسع'} من التمثيل البياني للدالة $g$"

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
        f"إزاحة {units(abs(h))} إلى {RIGHT if h > 0 else LEFT}، "
        f"و{units(abs(k))} إلى {UP if k > 0 else DOWN}"
    )


@variant("1.2", G10, example=3)
def vertex_and_axis_from_vertex_form(rng: random.Random) -> Problem:
    a = rng.choice([*INTEGER_SCALES, HALF, -HALF])
    h = nz(rng, -6, 6)
    k = rng.choice([n for n in range(-8, 9) if n not in (0, h, -h)])
    return Problem(
        "1.2",
        "حدّد إحداثيي رأس القطع المكافئ ومعادلة محور التماثل للدالة "
        f"$f(x)={vertex_form(a, h, k)}$.",
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
