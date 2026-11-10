"""تحويل مجموعة LaTeX التي تولّدها المسائل إلى معادلات Word الأصلية (OMML).

المجموعة محدودة عمدًا بما يستعمله المولّدون: كسور وجذور وقوى وأدلّة ونهايات وأقواس متحجّمة
ودوال مثلثية ورموز وحالات (cases). كل ما خرج عنها يُكتب نصًا مجرّدًا فلا ينكسر الملف.
المصفوفة (array) تعالجها الواجهة جدولًا لأن حدود الجدول لا تُمثَّل في OMML (انظر split_array).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from xml.sax.saxutils import escape, quoteattr

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MATH_FONT = "Cambria Math"

SYMBOLS = {
    "infty": "∞",
    "cdot": "⋅",
    "to": "→",
    "rightarrow": "→",
    "le": "≤",
    "leq": "≤",
    "ge": "≥",
    "geq": "≥",
    "pm": "±",
    "mp": "∓",
    "cup": "∪",
    "cap": "∩",
    "pi": "π",
    "circ": "∘",
    "times": "×",
    "div": "÷",
    "ne": "≠",
    "neq": "≠",
    "approx": "≈",
    "in": "∈",
    "ldots": "…",
    "dots": "…",
    "cdots": "⋯",
    "theta": "θ",
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "Delta": "Δ",
    "lambda": "λ",
    "mu": "μ",
    "sigma": "σ",
    "omega": "ω",
    "epsilon": "ε",
    "varepsilon": "ε",
    "phi": "φ",
    "Rightarrow": "⇒",
    "Leftrightarrow": "⇔",
    "forall": "∀",
    "exists": "∃",
    "emptyset": "∅",
    "prime": "′",
}
BLACKBOARD = {"R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ"}
FUNCTIONS = {
    "sin",
    "cos",
    "tan",
    "cot",
    "sec",
    "csc",
    "ln",
    "log",
    "exp",
    "arcsin",
    "arccos",
    "arctan",
    "max",
    "min",
}
SPACES = {",", ";", ":", " ", "!", ">", "quad", "qquad"}
SILENT = {"displaystyle", "textstyle", "limits", "nolimits", "right"}
TOKEN = re.compile(r"\\[a-zA-Z]+|\\.|[{}^_&]|\s+|.", re.S)


@dataclass
class Run:
    text: str
    plain: bool = False


def _run_xml(run: Run) -> str:
    props = '<m:rPr><m:sty m:val="p"/></m:rPr>' if run.plain else ""
    font = f'<w:rPr><w:rFonts w:ascii="{MATH_FONT}" w:hAnsi="{MATH_FONT}"/></w:rPr>'
    return f'<m:r>{props}{font}<m:t xml:space="preserve">{escape(run.text)}</m:t></m:r>'


def _xml(nodes: list) -> str:
    """يدمج الأحرف المتجاورة من النوع نفسه في تشغيلة واحدة ثم يسلسلها."""
    merged: list = []
    for node in nodes:
        if (
            isinstance(node, Run)
            and merged
            and isinstance(merged[-1], Run)
            and merged[-1].plain == node.plain
        ):
            merged[-1] = Run(merged[-1].text + node.text, node.plain)
        else:
            merged.append(node)
    return "".join(_run_xml(n) if isinstance(n, Run) else n for n in merged)


class _Parser:
    def __init__(self, source: str) -> None:
        self.tokens = TOKEN.findall(source)
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> str | None:
        token = self.peek()
        if token is not None:
            self.pos += 1
        return token

    def skip_space(self) -> None:
        while (token := self.peek()) is not None and token.isspace():
            self.pos += 1

    def group(self) -> list:
        """{...} أو ذرة واحدة."""
        self.skip_space()
        if self.peek() == "{":
            self.take()
            nodes = self.sequence(until="}")
            if self.peek() == "}":
                self.take()
            return nodes
        atom = self.atom()
        return [atom] if atom is not None else []

    def sequence(self, until: str | None = None) -> list:
        nodes: list = []
        while (token := self.peek()) is not None:
            if until is not None and token == until:
                break
            if token in ("\\right", "\\end"):
                break
            atom = self.atom()
            if atom is None:
                continue
            nodes.append(self.scripts(atom))
        return nodes

    def scripts(self, base):
        sub = sup = None
        while True:
            self.skip_space()
            token = self.peek()
            if token == "^" and sup is None:
                self.take()
                sup = self.group()
            elif token == "_" and sub is None:
                self.take()
                sub = self.group()
            else:
                break
        if sub is None and sup is None:
            return base
        e = f"<m:e>{_xml([base])}</m:e>"
        if sub is not None and sup is not None:
            return f"<m:sSubSup>{e}<m:sub>{_xml(sub)}</m:sub><m:sup>{_xml(sup)}</m:sup></m:sSubSup>"
        if sup is not None:
            return f"<m:sSup>{e}<m:sup>{_xml(sup)}</m:sup></m:sSup>"
        return f"<m:sSub>{e}<m:sub>{_xml(sub)}</m:sub></m:sSub>"

    def atom(self):
        token = self.take()
        if token is None or token.isspace() or token == "&":
            return None
        if token == "{":
            nodes = self.sequence(until="}")
            if self.peek() == "}":
                self.take()
            return _xml(nodes)
        if token.startswith("\\") and len(token) > 1:
            return self.command(token[1:])
        if token == "-":
            return Run("−")
        return Run(token)

    def command(self, name: str):
        if name in ("dfrac", "frac", "tfrac"):
            num, den = self.group(), self.group()
            return f"<m:f><m:num>{_xml(num)}</m:num><m:den>{_xml(den)}</m:den></m:f>"
        if name == "sqrt":
            return self.root()
        if name == "left":
            return self.delimited()
        if name == "lim":
            return self.limit()
        if name in SILENT:
            return None
        if name in ("text", "mbox", "mathrm", "operatorname"):
            return Run("".join(self.text_group()), plain=True)
        if name == "mathbb":
            return Run("".join(BLACKBOARD.get(c, c) for c in self.text_group()))
        if name == "begin":
            return self.environment()
        if name in FUNCTIONS:
            return Run(name, plain=True)
        if name in SYMBOLS:
            return Run(SYMBOLS[name])
        if name in SPACES:
            return Run(" ")
        if name in ("{", "}", "|", "%", "#", "&", "$"):
            return Run(name)
        return Run(name)

    def root(self):
        self.skip_space()
        degree = ""
        if self.peek() == "[":
            self.take()
            parts: list = []
            while self.peek() not in ("]", None):
                atom = self.atom()
                if atom is not None:
                    parts.append(atom)
            self.take()
            degree = f"<m:deg>{_xml(parts)}</m:deg>"
        body = self.group()
        props = "" if degree else '<m:radPr><m:degHide m:val="1"/></m:radPr>'
        return f"<m:rad>{props}{degree or '<m:deg/>'}<m:e>{_xml(body)}</m:e></m:rad>"

    def text_group(self) -> list[str]:
        self.skip_space()
        out: list[str] = []
        if self.peek() == "{":
            self.take()
            while self.peek() not in ("}", None):
                out.append(self.take() or "")
            self.take()
        else:
            out.append(self.take() or "")
        return out

    def limit(self):
        sub: list = []
        while True:
            self.skip_space()
            token = self.peek()
            if token in ("\\limits", "\\nolimits"):
                self.take()
            elif token == "_":
                self.take()
                sub = self.group()
            else:
                break
        if not sub:
            return Run("lim", plain=True)
        word = f"<m:e>{_xml([Run('lim', plain=True)])}</m:e>"
        return f"<m:limLow>{word}<m:lim>{_xml(sub)}</m:lim></m:limLow>"

    def delimited(self):
        opening = self.delimiter()
        body = self.sequence()
        if self.peek() == "\\right":
            self.take()
        closing = self.delimiter()
        return self.delim_xml(opening, closing, _xml(body))

    def delimiter(self) -> str:
        self.skip_space()
        token = self.take() or "."
        if token.startswith("\\"):
            token = {"\\{": "{", "\\}": "}", "\\|": "‖", "\\lvert": "|", "\\rvert": "|"}.get(token, "")
        return "" if token == "." else token

    @staticmethod
    def delim_xml(opening: str, closing: str, body: str) -> str:
        return (
            f"<m:d><m:dPr><m:begChr m:val={quoteattr(opening)}/><m:endChr m:val={quoteattr(closing)}/></m:dPr>"
            f"<m:e>{body}</m:e></m:d>"
        )

    def environment(self):
        name = "".join(self.text_group())
        rows = self.rows()
        if name == "cases":
            cols = max((len(row) for row in rows), default=1)
            lines = ""
            for row in rows:
                cells = "".join(
                    f"<m:e>{_xml(cell if i == 0 else [Run(chr(0x2003))] + cell)}</m:e>"
                    for i, cell in enumerate(row)
                )
                lines += f"<m:mr>{cells}</m:mr>"
            matrix = (
                f'<m:m><m:mPr><m:mcs><m:mc><m:mcPr><m:count m:val="{cols}"/><m:mcJc m:val="left"/></m:mcPr></m:mc></m:mcs>'
                f"</m:mPr>{lines}</m:m>"
            )
            return self.delim_xml("{", "", matrix)
        return _xml([item for row in rows for cell in row for item in cell])

    def rows(self) -> list[list[list]]:
        """يقرأ حتى \\end{...}: صفوف تفصلها \\\\ وخلايا تفصلها &."""
        rows: list[list[list]] = [[[]]]
        while (token := self.peek()) is not None:
            if token == "\\end":
                self.take()
                self.text_group()
                break
            if token == "\\\\":
                self.take()
                rows.append([[]])
            elif token == "&":
                self.take()
                rows[-1].append([])
            elif token == "\\hline":
                self.take()
            else:
                atom = self.atom()
                if atom is not None:
                    rows[-1][-1].append(self.scripts(atom))
        return rows


def to_omml(latex: str) -> str:
    """معادلة سطرية كاملة: عنصر m:oMath جاهز للإلحاق بفقرة."""
    nodes = _Parser(latex).sequence()
    return f'<m:oMath xmlns:m="{M_NS}" xmlns:w="{W_NS}">{_xml(nodes)}</m:oMath>'


ARRAY = re.compile(r"^(.*?)\\begin\{array\}\{([^}]*)\}(.*?)\\end\{array\}(.*)$", re.S)


@dataclass
class ArrayTable:
    spec: str
    rows: list[list[str]]
    rules_above: list[bool]  # \hline قبل الصف


def split_array(latex: str) -> tuple[str, ArrayTable, str] | None:
    """مصفوفة LaTeX (جدول قيم) → (ما قبلها، جدولها، ما بعدها)، أو None إن لم تكن مصفوفة."""
    match = ARRAY.match(latex.strip())
    if not match:
        return None
    before, spec, body, after = match.groups()
    rows: list[list[str]] = []
    rules: list[bool] = []
    for raw in re.split(r"\\\\", body):
        text = raw.replace("\\hline", "").strip()
        if not text:
            continue
        rows.append([cell.strip() for cell in text.split("&")])
        rules.append("\\hline" in raw)
    return before, ArrayTable(spec=spec, rows=rows, rules_above=rules), after
