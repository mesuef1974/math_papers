"""صيغ LaTeX رموزًا مقروءة حيث لا يعرض الملف معادلات (شرائح PPTX وخانات Word النصية): نقي حتمي بلا Django.

يحوّل مقاطع `$...$` وحدها ويترك النص العربي كما هو. الأسس والأدلة بالرموز العلوية والسفلية حين يملكها يونيكود وإلا
`^(..)` و`_(..)`، والكسر `a/b` أو `(a)/(b)`، والجذر `√`. كل مقطع بعزل من اليسار إلى اليمين (LRI وPDI) فلا يقلب اتجاه
الفقرة العربية ترتيب الرموز. ما لا يُحوَّل بأمان (مصفوفات وأوامر مجهولة) يعيد `None` من `convertible`، فيبقى سؤالًا نصيًّا.
"""

from __future__ import annotations

import re

from apps.papers.domain.bidi import LRI, PDI

MATH = re.compile(r"\$([^$]+)\$")
SIMPLE = re.compile(r"[\w.]+")

SUPERSCRIPT = str.maketrans("0123456789+-=()ni", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ")
SUBSCRIPT = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
SUPER_OK = frozenset("0123456789+-=()ni")
SUB_OK = frozenset("0123456789+-=()")

SYMBOLS = {
    "le": "≤",
    "leq": "≤",
    "ge": "≥",
    "geq": "≥",
    "ne": "≠",
    "neq": "≠",
    "cdot": "·",
    "times": "×",
    "div": "÷",
    "pm": "±",
    "mp": "∓",
    "infty": "∞",
    "pi": "π",
    "theta": "θ",
    "alpha": "α",
    "beta": "β",
    "Delta": "Δ",
    "to": "→",
    "rightarrow": "→",
    "approx": "≈",
    "sim": "~",
    "circ": "°",
    "angle": "∠",
    "triangle": "△",
    "perp": "⊥",
    "parallel": "∥",
    "cup": "∪",
    "cap": "∩",
    "emptyset": "∅",
    "in": "∈",
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "ln": "ln",
    "log": "log",
    "lim": "lim",
}
SPACING = frozenset({",", "!", ";", ":", " ", "quad", "qquad"})
TRANSPARENT = frozenset({"mathbb", "mathrm", "text", "operatorname", "mathbf", "overline"})
BLOCKERS = ("\\begin", "\\end", "\\hline", "&")


class _Reader:
    def __init__(self, text: str) -> None:
        self.s = text
        self.i = 0

    def done(self) -> bool:
        return self.i >= len(self.s)

    def group(self) -> str:
        """وسيط الأمر: `{...}` بتوازن الأقواس، وإلا الحرف التالي وحده."""
        while not self.done() and self.s[self.i] == " ":
            self.i += 1
        if self.done():
            return ""
        if self.s[self.i] != "{":
            ch = self.s[self.i]
            self.i += 1
            if ch == "\\":
                name = self.command_name()
                return f"\\{name}"
            return ch
        depth, start = 0, self.i + 1
        while self.i < len(self.s):
            if self.s[self.i] == "{":
                depth += 1
            elif self.s[self.i] == "}":
                depth -= 1
                if depth == 0:
                    inner = self.s[start : self.i]
                    self.i += 1
                    return inner
            self.i += 1
        raise ValueError("أقواس غير متوازنة")

    def command_name(self) -> str:
        j = self.i
        if j < len(self.s) and self.s[j].isalpha():
            while j < len(self.s) and self.s[j].isalpha():
                j += 1
        else:
            j = min(j + 1, len(self.s))
        name, self.i = self.s[self.i : j], j
        return name


def _wrap(text: str) -> str:
    return text if SIMPLE.fullmatch(text) or len(text) <= 1 else f"({text})"


def _script(content: str, ok: frozenset[str], table: dict[int, int], mark: str) -> str:
    content = content.strip()
    if content and all(c in ok for c in content):
        return content.translate(table)
    return f"{mark}({content})" if len(content) > 1 else f"{mark}{content}"


def _convert(latex: str) -> str:
    r = _Reader(latex)
    out: list[str] = []
    while not r.done():
        ch = r.s[r.i]
        r.i += 1
        if ch == "\\":
            name = r.command_name()
            if name in ("frac", "dfrac", "tfrac"):
                num, den = _convert(r.group()), _convert(r.group())
                out.append(f"{_wrap(num)}/{_wrap(den)}")
            elif name == "sqrt":
                index = ""
                if not r.done() and r.s[r.i] == "[":
                    end = r.s.index("]", r.i)
                    index = _script(r.s[r.i + 1 : end], SUPER_OK, SUPERSCRIPT, "^")
                    r.i = end + 1
                radicand = _convert(r.group())
                out.append(f"{index}√{_wrap(radicand)}")
            elif name in ("left", "right"):
                delimiter = r.group()
                out.append("" if delimiter == "." else delimiter.lstrip("\\") if delimiter != "\\{" else "{")
            elif name in TRANSPARENT:
                out.append(_convert(r.group()))
            elif name == "limits":
                continue
            elif name in SPACING:
                out.append(" ")
            elif name in SYMBOLS:
                out.append(SYMBOLS[name])
            elif name in ("{", "}", "|"):
                out.append(name)
            else:
                out.append(f"\\{name}")  # مجهول: يبقى فيرفضه `convertible`
        elif ch == "^":
            out.append(_script(_convert(r.group()), SUPER_OK, SUPERSCRIPT, "^"))
        elif ch == "_":
            out.append(_script(_convert(r.group()), SUB_OK, SUBSCRIPT, "_"))
        elif ch in "{}":
            continue
        else:
            out.append(ch)
    return re.sub(r" {2,}", " ", "".join(out)).strip()


def convertible(text: str) -> bool:
    """النص يخلو من مصفوفات وأوامر لا يعرفها المحوّل (ومن `$` غير مزدوج)."""
    if any(b in text for b in BLOCKERS):
        return False
    try:
        converted = plain_math(text)
    except (ValueError, IndexError):
        return False
    return "\\" not in converted and "$" not in converted


def plain_math(text: str) -> str:
    """النص بعد تحويل كل مقطع `$...$` إلى رموز مقروءة بعزل LTR؛ وما خارج المقاطع كما هو."""
    return MATH.sub(lambda m: f"{LRI}{_convert(m.group(1))}{PDI}", text)
