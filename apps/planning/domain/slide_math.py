"""تقسيم نص الشريحة إلى نص عادي ومعادلات: المصدر الوحيد لقرار «ما الذي يُكتب معادلة» في عرض PPTX. نقي بلا Django.

المعادلة مقطع `$...$` من المولّدات، أو صيغة مكتوبة برموز يونيكود داخل النص العربي (الأهداف المعتمدة: «f(x) = ax²»)
فتُحوَّل إلى LaTeX. كلتاهما تصير معادلة PowerPoint أصلية؛ ولو بقيت نصًّا في فقرة من اليمين لانقلب ترتيب رموزها.
"""

from __future__ import annotations

import re

from apps.papers.domain.bidi import isolate_number_ranges, strip_isolation

from .plain_math import MATH, SUB_OK, SUBSCRIPT, SUPER_OK, SUPERSCRIPT, plain_math

FUNCTION_NAMES = ("arcsin", "arccos", "arctan", "sin", "cos", "tan", "cot", "sec", "csc", "ln", "log", "lim")
_SUPER = {c.translate(SUPERSCRIPT): c for c in SUPER_OK} | {"ˣ": "x"}
_SUB = {c.translate(SUBSCRIPT): c for c in SUB_OK}
_STRONG = "=<>≤≥≠≈±^√′∞→·×÷" + "".join((*_SUPER, *_SUB))
_CHARS = "A-Za-z0-9Ͱ-Ͽ+\\-−*/()\\[\\]|.,'°" + re.escape(_STRONG)
CANDIDATE = re.compile(f"[{_CHARS}](?:[{_CHARS} ]*[{_CHARS}])?")
_FUNCTION = re.compile(rf"(?<![A-Za-z])(?:{'|'.join(FUNCTION_NAMES)})(?![A-Za-z])")
_CALL = re.compile(r"(?<![A-Za-z])[a-zA-Z]′?\(")
_VARIABLE = re.compile(r"(?<![A-Za-z])[a-zA-Z](?![A-Za-z])")


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    """يُخرج من المقطع ترقيم الجملة وقوسًا بلا نظير عند طرفيه."""
    while start < end:
        piece = text[start:end]
        if piece[0] in " .,":
            start += 1
        elif piece[-1] in " .,":
            end -= 1
        elif piece[0] in ")]" or (piece[0] in "([" and piece.count("(") > piece.count(")")):
            start += 1
        elif piece[-1] in "([" or (piece[-1] in ")]" and piece.count(")") > piece.count("(")):
            end -= 1
        else:
            break
    return start, end


def _is_math(piece: str) -> bool:
    if any(c in _STRONG for c in piece) or _FUNCTION.search(piece) or _CALL.search(piece):
        return True
    return bool(_VARIABLE.search(piece))


def _group(text: str, i: int) -> tuple[str, int]:
    """ما يلي `^` أو `_` أو `√`: قوس متوازن (بلا قوسيه) أو رقم أو حرف واحد."""
    if i < len(text) and text[i] == "(":
        depth = 0
        for j in range(i, len(text)):
            depth += {"(": 1, ")": -1}.get(text[j], 0)
            if depth == 0:
                return text[i + 1 : j], j + 1
    number = re.compile(r"\d+").match(text, i)
    if number:
        return number.group(0), number.end()
    return text[i : i + 1], i + 1


def unicode_latex(text: str) -> str:
    """صيغة يونيكود إلى LaTeX الذي يفهمه محوّل OMML."""
    out: list[str] = []
    i = 0
    while i < len(text):
        c = text[i]
        function = _FUNCTION.match(text, i)
        if function:
            out.append(f"\\{function.group(0)} ")
            i = function.end()
        elif c in _SUPER or c in _SUB:
            table, mark = (_SUPER, "^") if c in _SUPER else (_SUB, "_")
            j = i
            while j < len(text) and text[j] in table:
                j += 1
            out.append(mark + "{" + "".join(table[x] for x in text[i:j]) + "}")
            i = j
        elif c in "^_√":
            body, i = _group(text, i + 1)
            head = "\\sqrt" if c == "√" else c
            out.append(f"{head}{{{unicode_latex(body)}}}")
        else:
            out.append("-" if c == "−" else c)
            i += 1
    return "".join(out)


def _bare(text: str) -> list[tuple[bool, str]]:
    out: list[tuple[bool, str]] = []
    last = 0
    for match in CANDIDATE.finditer(text):
        start, end = _trim(text, match.start(), match.end())
        if start >= end or not _is_math(text[start:end]):
            continue
        out += [(False, text[last:start]), (True, unicode_latex(text[start:end]))]
        last = end
    return [*out, (False, text[last:])]


def segments(text: str) -> list[tuple[bool, str]]:
    """(معادلة؟، المحتوى) بترتيب القراءة: المعادلة LaTeX بلا `$`، وغيرها نص كما هو."""
    out: list[tuple[bool, str]] = []
    for i, part in enumerate(MATH.split(text)):
        if i % 2:
            out.append((True, strip_isolation(part)))
        else:
            out += _bare(part)
    return [(is_math, part) for is_math, part in out if part]


def isolate_outside_math(text: str) -> str:
    """`isolate_number_ranges` لما خارج `$...$` وحده: علامات العزل لا تدخل LaTeX."""
    return "".join(
        f"${part}$" if i % 2 else isolate_number_ranges(part) for i, part in enumerate(MATH.split(text))
    )


def display(text: str) -> str:
    """النص كما يُقرأ دون معادلات أصلية (الملاحظات والبديل لقارئ لا يعرضها)."""
    return plain_math(text)
