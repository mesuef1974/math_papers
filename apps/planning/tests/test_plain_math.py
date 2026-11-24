"""تحويل LaTeX إلى رموز مقروءة لشرائح البنود: الأسس والكسور والجذور والمقارنات والدوال والمتداخل، وما لا يُحوَّل يُرفض."""

import pytest

from apps.papers.domain.bidi import LRI, PDI, strip_isolation
from apps.planning.domain.plain_math import convertible, plain_math


def conv(text: str) -> str:
    return strip_isolation(plain_math(text))


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        (r"$f(x)=-5x^2$", "f(x)=-5x²"),
        (r"$x^{-1}$", "x⁻¹"),
        (r"$x^{2n}$", "x²ⁿ"),
        (r"$x^{a+b}$", "x^(a+b)"),
        (r"$90^\circ$", "90°"),
        (r"$\angle A = 45^{\circ}$", "∠ A = 45°"),
        (r"$a_1$", "a₁"),
        (r"$\frac{1}{2}x^2$", "1/2x²"),
        (r"$\dfrac{x+1}{x-2}$", "(x+1)/(x-2)"),
        (r"$\sqrt{x}$", "√x"),
        (r"$\sqrt{2x+1}$", "√(2x+1)"),
        (r"$\sqrt[3]{x}$", "³√x"),
        (r"$0 \le x \le 2$", "0 ≤ x ≤ 2"),
        (r"$x \ge 3 \cdot 2 \times 4$", "x ≥ 3 · 2 × 4"),
        (r"$\left(x+1\right)^2$", "(x+1)²"),
        (r"$\lim_{x\to 2} f(x)$", "lim_(x→ 2) f(x)"),
        (r"$\mathbb{R}$", "R"),
        (r"$\sin x + \pi$", "sin x + π"),
        (r"$\dfrac{\sqrt{3}}{2}$", "(√3)/2"),
    ],
)
def test_conversions(latex, expected):
    assert conv(latex) == expected


def test_arabic_text_outside_math_is_untouched_and_each_segment_is_ltr_isolated():
    text = r"أوجد قيمة $x^2$ و $\frac{1}{3}$ ثم صف."
    out = plain_math(text)
    assert out.startswith("أوجد قيمة ") and out.endswith(" ثم صف.")
    assert out.count(LRI) == 2 and out.count(PDI) == 2
    assert strip_isolation(out) == "أوجد قيمة x² و 1/3 ثم صف."


@pytest.mark.parametrize(
    "text", [r"$\begin{array}{c} 1 \end{array}$", r"$\unknowncmd{x}$", r"$a & b$", "$x^2"]
)
def test_unsafe_math_is_not_convertible(text):
    assert not convertible(text)


def test_plain_text_and_clean_math_are_convertible():
    assert convertible("جملة عربية بلا صيغة")
    assert convertible(r"$\dfrac{x}{2}+\sqrt{x}$")
