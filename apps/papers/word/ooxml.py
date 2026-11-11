"""أدوات OOXML منخفضة المستوى: تشغيلات وفقرات وجداول بترتيب عناصر صحيح (Word يتسامح، لكن LibreOffice لا)."""

from __future__ import annotations

import re
from io import BytesIO
from xml.sax.saxutils import escape

from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm
from docx.table import _Cell
from docx.text.paragraph import Paragraph

from .omml import to_omml

FONT = "Arial"
SYMBOL_FONT = "Segoe UI Symbol"
LRM = "‎"
RLM = "‏"
INK = "000000"
SOFT = "595959"
RULE = "808080"
SHADE = "EDEDED"
W = nsdecls("w")
ARABIC = re.compile(r"[؀-ۿݐ-ݿ]")


def twips(cm: float) -> int:
    return round(cm * 567)


def rpr(
    size: float | None = None,
    bold: bool = False,
    italic: bool = False,
    color: str | None = None,
    font: str = FONT,
    rtl: bool = False,
) -> str:
    parts = [f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}" w:eastAsia="{font}"/>']
    if bold:
        parts.append("<w:b/><w:bCs/>")
    if italic:
        parts.append("<w:i/><w:iCs/>")
    if color:
        parts.append(f'<w:color w:val="{color}"/>')
    if size:
        half = round(size * 2)
        parts.append(f'<w:sz w:val="{half}"/><w:szCs w:val="{half}"/>')
    if rtl:
        parts.append("<w:rtl/>")
    return f"<w:rPr>{''.join(parts)}</w:rPr>"


def add_text(paragraph: Paragraph, text: str, **fmt) -> None:
    """نص عادي؛ الأجزاء العربية تُعلَّم rtl حتى يطبّق Word خط وحجم النص المعقّد."""
    if not text:
        return
    force_rtl = fmt.pop("force_rtl", False)
    for chunk in re.split(r"(\t)", text):
        if chunk == "\t":
            paragraph._p.append(parse_xml(f"<w:r {W}><w:tab/></w:r>"))
        elif chunk:
            rtl = force_rtl or bool(ARABIC.search(chunk))
            xml = f'<w:r {W}>{rpr(rtl=rtl, **fmt)}<w:t xml:space="preserve">{escape(chunk)}</w:t></w:r>'
            paragraph._p.append(parse_xml(xml))


def add_math(paragraph: Paragraph, latex: str) -> None:
    paragraph._p.append(parse_xml(to_omml(latex)))


def add_picture(paragraph: Paragraph, png: bytes, width_cm: float) -> None:
    paragraph.add_run().add_picture(BytesIO(png), width=Cm(width_cm))


def add_field(paragraph: Paragraph, instruction: str, **fmt) -> None:
    paragraph._p.append(
        parse_xml(
            f'<w:fldSimple {W} w:instr="{instruction}"><w:r>{rpr(**fmt)}<w:t>1</w:t></w:r></w:fldSimple>'
        )
    )


def _ppr(
    align: str | None,
    rtl: bool,
    before: float,
    after: float,
    line: float | None,
    keep_next: bool,
    keep_lines: bool,
    page_break: bool,
    bottom: tuple[str, int] | None,
    top: tuple[str, int] | None,
    shade: str | None,
    indent_cm: float,
    exact_pt: float | None,
) -> str:
    parts: list[str] = []
    if keep_next:
        parts.append("<w:keepNext/>")
    if keep_lines:
        parts.append("<w:keepLines/>")
    if page_break:
        parts.append("<w:pageBreakBefore/>")
    if bottom or top:
        edges = ""
        if top:
            edges += f'<w:top w:val="{top[0]}" w:sz="{top[1]}" w:space="2" w:color="{RULE if top[0] != "single" else INK}"/>'
        if bottom:
            edges += (
                f'<w:bottom w:val="{bottom[0]}" w:sz="{bottom[1]}" w:space="2" '
                f'w:color="{RULE if bottom[0] != "single" else INK}"/>'
            )
        parts.append(f"<w:pBdr>{edges}</w:pBdr>")
    if shade:
        parts.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>')
    if rtl:
        parts.append("<w:bidi/>")
    spacing = f'<w:spacing w:before="{round(before * 20)}" w:after="{round(after * 20)}"'
    if exact_pt:
        spacing += f' w:line="{round(exact_pt * 20)}" w:lineRule="exact"'
    elif line:
        spacing += f' w:line="{round(line * 240)}" w:lineRule="auto"'
    parts.append(spacing + "/>")
    if indent_cm:
        parts.append(f'<w:ind w:start="{twips(indent_cm)}"/>')
    if align:
        parts.append(f'<w:jc w:val="{align}"/>')
    return f"<w:pPr>{''.join(parts)}</w:pPr>"


def _reusable(paragraph: Paragraph) -> bool:
    return len(paragraph._p) == 0


def new_paragraph(
    container,
    *,
    align: str | None = None,
    rtl: bool = True,
    before: float = 0,
    after: float = 3,
    line: float | None = 1.15,
    keep_next: bool = False,
    keep_lines: bool = True,
    page_break: bool = False,
    bottom: tuple[str, int] | None = None,
    top: tuple[str, int] | None = None,
    shade: str | None = None,
    indent_cm: float = 0,
    exact_pt: float | None = None,
) -> Paragraph:
    """فقرة جديدة (أو الفقرة الفارغة الأولى في خلية). align: center/right/left/both كما في OOXML؛
    في الفقرة العربية يعني left الطرف الأيسر حقًا (right الطرف الأيمن)، فلا خلط مع start/end."""
    if isinstance(container, _Cell) and len(container.paragraphs) == 1 and _reusable(container.paragraphs[0]):
        paragraph = container.paragraphs[0]
    else:
        paragraph = container.add_paragraph()
    xml = _ppr(
        align,
        rtl,
        before,
        after,
        line,
        keep_next,
        keep_lines,
        page_break,
        bottom,
        top,
        shade,
        indent_cm,
        exact_pt,
    )
    paragraph._p.insert(0, parse_xml(xml.replace("<w:pPr>", f"<w:pPr {W}>", 1)))
    return paragraph


def spacer(container, points: float = 4, page_break: bool = False, keep_next: bool = False) -> Paragraph:
    return new_paragraph(
        container, before=0, after=0, line=None, exact_pt=points, page_break=page_break, keep_next=keep_next
    )


# ---------- الجداول ----------

BORDER = {"val": "single", "sz": 6, "color": INK}
NONE = {"val": "nil"}


def _edges(spec: dict | None, tag: str) -> str:
    if not spec:
        return ""
    out = ""
    for side in ("top", "start", "bottom", "end", "left", "right", "insideH", "insideV"):
        edge = spec.get(side)
        if edge is None:
            continue
        if edge.get("val") == "nil":
            out += f'<w:{side} w:val="nil"/>'
        else:
            out += (
                f'<w:{side} w:val="{edge["val"]}" w:sz="{edge["sz"]}" w:space="0" w:color="{edge["color"]}"/>'
            )
    return f"<w:{tag}>{out}</w:{tag}>" if out else ""


def box(sz: int = 6, color: str = INK, inside: bool = True) -> dict:
    edge = {"val": "single", "sz": sz, "color": color}
    spec = {"top": edge, "left": edge, "bottom": edge, "right": edge}
    if inside:
        spec.update({"insideH": edge, "insideV": edge})
    return spec


def make_table(
    container,
    rows: int,
    widths_cm: list[float],
    *,
    rtl: bool = True,
    borders: dict | None = None,
    align: str = "center",
    cell_margin_cm: float = 0.12,
):
    """جدول بعرض ثابت؛ rtl يجعل العمود الأول في أقصى اليمين (bidiVisual)."""
    table = container.add_table(rows=rows, cols=len(widths_cm))
    total = sum(twips(w) for w in widths_cm)
    margin = twips(cell_margin_cm)
    tbl_pr = (
        f"<w:tblPr {W}>"
        + ("<w:bidiVisual/>" if rtl else "")
        + f'<w:tblW w:w="{total}" w:type="dxa"/><w:jc w:val="{align}"/>'
        + _edges(borders, "tblBorders")
        + '<w:tblLayout w:type="fixed"/>'
        + f'<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="{margin}" w:type="dxa"/>'
        f'<w:bottom w:w="40" w:type="dxa"/><w:right w:w="{margin}" w:type="dxa"/></w:tblCellMar>'
        + '<w:tblLook w:val="0000"/></w:tblPr>'
    )
    element = table._tbl
    element.remove(element.tblPr)
    element.insert(0, parse_xml(tbl_pr))
    grid = element.tblGrid
    for column, width in zip(grid.findall(qn("w:gridCol")), widths_cm, strict=True):
        column.set(qn("w:w"), str(twips(width)))
    for row in table.rows:
        for cell, width in zip(row.cells, widths_cm, strict=True):
            set_cell(cell, width)
    return table


def set_cell(
    cell: _Cell,
    width_cm: float,
    *,
    borders: dict | None = None,
    shade: str | None = None,
    valign: str = "center",
    span: int = 0,
) -> None:
    tc = cell._tc
    existing = tc.tcPr
    if existing is not None:
        tc.remove(existing)
    xml = f'<w:tcPr {W}><w:tcW w:w="{twips(width_cm)}" w:type="dxa"/>'
    if span:
        xml += f'<w:gridSpan w:val="{span}"/>'
    xml += _edges(borders, "tcBorders")
    if shade:
        xml += f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>'
    xml += f'<w:vAlign w:val="{valign}"/></w:tcPr>'
    tc.insert(0, parse_xml(xml))


def set_row(
    row, *, height_cm: float | None = None, exact: bool = False, header: bool = False, cant_split: bool = True
) -> None:
    tr = row._tr
    existing = tr.trPr
    if existing is not None:
        tr.remove(existing)
    xml = f"<w:trPr {W}>"
    if cant_split:
        xml += "<w:cantSplit/>"
    if height_cm:
        xml += f'<w:trHeight w:val="{twips(height_cm)}" w:hRule="{"exact" if exact else "atLeast"}"/>'
    if header:
        xml += "<w:tblHeader/>"
    xml += "</w:trPr>"
    index = 1 if tr.tblPrEx is not None else 0
    tr.insert(index, parse_xml(xml))
