"""أدوات OOXML منخفضة المستوى: تشغيلات وفقرات وجداول بترتيب عناصر صحيح (Word يتسامح، لكن LibreOffice لا)."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.section import _Footer, _Header
from docx.shared import Cm
from docx.table import _Cell
from docx.text.paragraph import Paragraph
from lxml import etree

from .omml import to_omml

# خط الورقة الموحَّد مع الطباعة وPDF (frontend/src/styles/fonts.css): يُضمَّن في الملف فيظهر على أي جهاز
FONT = "Noto Naskh Arabic"
FONT_DIR = Path(__file__).parent / "assets" / "fonts"
# عنصر جدول الخطوط ← (ملف TrueType، مفتاح التعمية). المفاتيح ثابتة ليخرج الملف نفسه من الحمولة نفسها.
EMBEDDED_FONTS = {
    "embedRegular": ("NotoNaskhArabic-Regular.ttf", "{9C20DED5-8C46-4DE9-B0C9-CAA3B576D2E2}"),
    "embedBold": ("NotoNaskhArabic-Bold.ttf", "{12CBF5B2-DA98-4F56-A2A0-986736CBCAD5}"),
}
OBFUSCATED_FONT = "application/vnd.openxmlformats-officedocument.obfuscatedFont"
# Word يقيس السطر «المفرد» بارتفاع الخط الطبيعي لا بحجمه. الخط يرفع USE_TYPO_METRICS، فارتفاعه
# (sTypoAscender - sTypoDescender + sTypoLineGap) / unitsPerEm = 1.703 من حجمه. المضاعف الافتراضي يعيد السطر
# إلى ارتفاع سطر الطباعة (`--leading-body` في print.css).
FONT_NATURAL_LINE = 1.703
PRINT_LEADING = 1.6
LINE_MULTIPLE = round(PRINT_LEADING / FONT_NATURAL_LINE, 3)
SYMBOL_FONT = "Segoe UI Symbol"
LRM = "‎"
RLM = "‏"
# ألوان هوية «أوراق» على الورق: النص حبر أسود، والعنابي للعناوين والشارات والخطوط الرئيسة، والذهبي للتزيين
INK = "000000"
SOFT = "4C535C"
RULE = "7D848E"
LINE = "B5BBC4"
BRAND = "8E2433"
BRAND_STRONG = "6F1137"
SHADE = "F0DFE3"  # العنابي الخفيف: خلفية الملاحظات وخانات الأرقام
ACCENT = "E3AB3C"
WHITE = "FFFFFF"
W = nsdecls("w")
SWAPPED = {"left": "right", "right": "left"}
ARABIC = re.compile(r"[؀-ۿݐ-ݿ]")


def obfuscate_font(data: bytes, key: str) -> bytes:
    """تعمية الخط المضمَّن كما يطلب Word (ECMA-376 الجزء 4، 2.8.1): أول 32 بايتًا XOR مع بايتات المفتاح معكوسة.
    العملية عكس نفسها، فتطبيقها مرتين يعيد الملف الأصلي."""
    mask = bytes.fromhex(key.strip("{}").replace("-", ""))[::-1]
    return bytes(b ^ mask[i % 16] for i, b in enumerate(data[:32])) + data[32:]


def embed_fonts(doc) -> None:
    """يضمّن خط الورقة بوزنيه في الوثيقة: جزء معمًّى لكل وزن، وإحالته في جدول الخطوط، وإعداد يبقيه عند إعادة الحفظ."""
    table = next(rel.target_part for rel in doc.part.rels.values() if rel.reltype == RT.FONT_TABLE)
    fonts = parse_xml(table.blob)
    for old in fonts.findall(qn("w:font")):
        if old.get(qn("w:name")) == FONT:
            fonts.remove(old)
    refs = []
    for index, (tag, (filename, key)) in enumerate(EMBEDDED_FONTS.items(), start=1):
        part = Part(
            PackURI(f"/word/fonts/font{index}.odttf"),
            OBFUSCATED_FONT,
            obfuscate_font((FONT_DIR / filename).read_bytes(), key),
            doc.part.package,
        )
        refs.append(f'<w:{tag} r:id="{table.relate_to(part, RT.FONT)}" w:fontKey="{key}"/>')
    fonts.append(
        parse_xml(
            f'<w:font {nsdecls("w", "r")} w:name="{FONT}"><w:charset w:val="B2"/><w:family w:val="roman"/>'
            f'<w:pitch w:val="variable"/>{"".join(refs)}</w:font>'
        )
    )
    table._blob = etree.tostring(fonts, xml_declaration=True, encoding="UTF-8", standalone=True)
    settings = doc.settings.element
    if settings.find(qn("w:embedTrueTypeFonts")) is None:
        # موضعه في مخطط الإعدادات بعد العناصر الآتية وقبل ما سواها
        before = {
            qn(f"w:{name}")
            for name in (
                "writeProtection", "view", "zoom", "removePersonalInformation", "removeDateAndTime",
                "doNotDisplayPageBoundaries", "displayBackgroundShape", "printPostScriptOverText",
                "printFractionalCharacterWidth", "printFormsData",
            )
        }  # fmt: skip
        position = sum(1 for child in settings if child.tag in before)
        settings.insert(position, parse_xml(f"<w:embedTrueTypeFonts {nsdecls('w')}/>"))


def twips(cm: float) -> int:
    return round(cm * 567)


def rpr(
    size: float | None = None,
    bold: bool = False,
    italic: bool = False,
    color: str | None = None,
    font: str = FONT,
    rtl: bool = False,
    fill: str | None = None,
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
    if fill:
        parts.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>')
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
    bottom: tuple | None,
    top: tuple | None,
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
        # الحافة (النمط، السمك[، اللون])؛ بلا لون: أسود للخط المتصل ورمادي لغيره
        edges = ""
        for side, edge in (("top", top), ("bottom", bottom)):
            if edge:
                color = edge[2] if len(edge) > 2 else (RULE if edge[0] != "single" else INK)
                edges += f'<w:{side} w:val="{edge[0]}" w:sz="{edge[1]}" w:space="2" w:color="{color}"/>'
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
        # Word يقرأ left/right في الفقرة العربية (bidi) بمعنى البداية/النهاية، أي معكوسين؛ نعكسهما هنا
        # فيبقى معنى align في هذه الوحدة فيزيائيًا: left الطرف الأيسر دائمًا.
        if rtl and align in SWAPPED:
            align = SWAPPED[align]
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
    line: float | None = LINE_MULTIPLE,
    keep_next: bool = False,
    keep_lines: bool = True,
    page_break: bool = False,
    bottom: tuple | None = None,
    top: tuple | None = None,
    shade: str | None = None,
    indent_cm: float = 0,
    exact_pt: float | None = None,
) -> Paragraph:
    """فقرة جديدة (أو الفقرة الفارغة الأولى في خلية). align: center/right/left/both؛
    left الطرف الأيسر حقًا وright الأيمن في الفقرة العربية واللاتينية معًا (العكس الذي يطلبه Word يتم في _ppr)."""
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
BRAND_EDGE = {"val": "single", "sz": 10, "color": BRAND}
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
    if isinstance(container, _Footer | _Header):
        table = container.add_table(rows, len(widths_cm), Cm(sum(widths_cm)))
    else:
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
