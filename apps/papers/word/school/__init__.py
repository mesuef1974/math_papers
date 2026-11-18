"""ورقة الاختبار في Word بقالب المدرسة (قرار المالك 2026-11-18): خيار إضافي بجانب إخراج «أوراق».

الغلاف مأخوذ كما هو من ملف قالب المدرسة (`assets/school/cover.docx`: شعار الوزارة والمثلث وجدول الرصد والتعليمات،
مجرّدًا من الأسئلة، وحقوله رموز مثل {school} تُملأ من الورقة). الأسئلة تُبنى بنسق القالب: كل سؤال إطار بشريط رمادي
«السؤال رقم (n) | الدرجة (m)»، والبدائل عمودية بحرف في مربع، والمقالي مستطيل «وضح خطوات الحل»، والتذييل «صفحة n من N»
لكل نموذج. المحتوى (النص والمعادلات OMML والرسوم) هو نفسه في إخراج «أوراق».
"""

from __future__ import annotations

import copy
import re
from io import BytesIO
from itertools import count
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.oxml import parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm

from .. import ooxml as x
from ..graph_png import render_graph
from .fill import fill

COVER = (Path(__file__).parent.parent / "assets" / "school" / "cover.docx").read_bytes()
MARGIN_CM = 1.27  # هوامش القالب (720 twips)؛ الغلاف مثبَّت عليها
CONTENT_CM = 21 - 2 * MARGIN_CM
HEAD = "BFBFBF"  # رمادي شريط السؤال كما في القالب
BOX = "A6A6A6"
LETTERS = "ABCD"
ORDINALS = {
    "الأول": 1,
    "الثاني": 2,
    "الثالث": 3,
    "الرابع": 4,
    "الخامس": 5,
    "السادس": 6,
    "السابع": 7,
    "الثامن": 8,
    "التاسع": 9,
    "العاشر": 10,
    "الحادي عشر": 11,
    "الثاني عشر": 12,
}
YEAR = re.compile(r"(\d{4})\s*[-–/]\s*(\d{4})")
DOC_PR = qn("wp:docPr")
SECTION_TAGS = (qn("w:sectPr"),)
# ما يلي w:bidi في ترتيب عناصر pPr (المخطط يفرض الترتيب)
AFTER_BIDI = tuple(
    qn(f"w:{name}")
    for name in (
        "adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc "
        "textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange"
    ).split()
)


def _explicit_bidi(paragraph) -> None:
    """فقرة الغلاف ترث الاتجاه من نمط Normal في القالب؛ يُكتب صريحًا فيها قبل نزعه من النمط."""
    ppr = paragraph.find(qn("w:pPr"))
    if ppr is None:
        ppr = parse_xml(f"<w:pPr {x.W}/>")
        paragraph.insert(0, ppr)
    if ppr.find(qn("w:bidi")) is not None:
        return
    bidi = parse_xml(f"<w:bidi {x.W}/>")
    later = next((child for child in ppr if child.tag in AFTER_BIDI), None)
    if later is None:
        ppr.append(bidi)
    else:
        later.addprevious(bidi)


def _blank(element) -> bool:
    return (
        element.tag == qn("w:p")
        and not "".join(element.itertext()).strip()
        and next(element.iter(qn("w:drawing"), qn("w:pict")), None) is None
    )


def new_document():
    """وثيقة من ملف القالب: يُحفظ الغلاف الأصلي جانبًا ويُفرَّغ المتن (يبقى sectPr بهوامشه)."""
    doc = Document(BytesIO(COVER))
    body = doc.element.body
    pristine = [element for element in body if element.tag not in SECTION_TAGS]
    for element in pristine:
        body.remove(element)
    while pristine and _blank(
        pristine[-1]
    ):  # فقرتا الفراغ قبل فاصل الصفحة في الأصل تدفعان آخر تعليمة إلى صفحة ثانية
        pristine.pop()
    # نمط Normal في القالب عربي الاتجاه، فالفقرة اللاتينية (البدائل) تنعكس محاذاتها؛ الاتجاه يُنقل إلى فقرات الغلاف
    for element in pristine:
        for paragraph in [element] if element.tag == qn("w:p") else []:
            _explicit_bidi(paragraph)
        for paragraph in element.iter(qn("w:p")):
            _explicit_bidi(paragraph)
    normal = doc.styles["Normal"].element.find(qn("w:pPr"))
    if normal is not None:
        for bidi in normal.findall(qn("w:bidi")):
            normal.remove(bidi)
    doc._school_cover = pristine  # type: ignore[attr-defined]
    doc._school_ids = count(1000)  # type: ignore[attr-defined]
    return doc


def grade_number(grade: str) -> str:
    name = re.sub(r"^الصف\s+", "", grade).strip()
    digits = re.match(r"\d+", name)
    if digits:
        return digits.group(0)
    for words in sorted(ORDINALS, key=len, reverse=True):
        if name.startswith(words):
            return str(ORDINALS[words])
    return ""


def count_line(mcq: int, essay: int) -> str:
    total = mcq + essay
    return (
        f"تأكد من أن الاختبار مكون من {total} سؤالًا: {mcq} من أسئلة الاختيار من متعدد"
        f" و{essay} من الأسئلة المقالية."
    )


def cover_values(header: dict, paper: dict, duration: str) -> dict[str, str]:
    title = re.sub("[‎‏]", "", paper["title"])
    exam = title.split(":")[0].strip()
    year = YEAR.search(title)
    questions = paper["questions"]
    mcq = sum(q["kind"] == "mcq" for q in questions)
    grade = header["grade"]
    number = grade_number(grade)
    names = {str(v): k for k, v in ORDINALS.items()}
    grade_words = f"الصف {names[number]}" if number in names else grade
    subject = (
        f"مادة {header['subject']} لل{grade_words.removeprefix('ال')}"
        if grade
        else f"مادة {header['subject']}"
    )
    if header["form"]:
        exam = f"{exam} (النموذج {header['form']})"
    return {
        "{school}": header["school"],
        "{exam}": exam,
        "{subject}": subject,
        "{year}": f"{year.group(1)} / {year.group(2)}" if year else "",
        "{minutes}": duration,
        "{total}": str(paper["total_marks"]),
        "{grade}": grade_number(grade),
        "{count_line}": count_line(mcq, len(questions) - mcq),
    }


def _score_rows(table, paper: dict) -> None:
    """صفوف جدول الرصد: الموضوعي صف واحد بمداه ومجموعه، ثم صف لكل سؤال مقالي."""
    rows = table.findall(qn("w:tr"))
    head, proto, total = rows[0], rows[1], rows[2]
    rpr = next(head.iter(qn("w:rPr")), None)
    questions = paper["questions"]
    mcq = [q for q in questions if q["kind"] == "mcq"]
    entries = []
    if mcq:
        first, last = mcq[0]["number"], mcq[-1]["number"]
        entries.append((f"{first} – {last}" if first != last else str(first), sum(q["marks"] for q in mcq)))
    entries += [(str(q["number"]), q["marks"]) for q in questions if q["kind"] != "mcq"]
    for label, marks in entries:
        row = copy.deepcopy(proto)
        cells = row.findall(qn("w:tc"))
        for cell, text in zip(cells, (label, str(marks)), strict=False):
            paragraph = cell.find(qn("w:p"))
            run = parse_xml(f'<w:r {x.W}><w:t xml:space="preserve"></w:t></w:r>')
            if rpr is not None:
                run.insert(0, copy.deepcopy(rpr))
            run.find(qn("w:t")).text = x.LRM + text if "–" in text else text
            paragraph.append(run)
        total.addprevious(row)
    table.remove(proto)


def cover(doc, header: dict, paper: dict, duration: str) -> None:
    body = doc.element.body
    elements = [copy.deepcopy(element) for element in doc._school_cover]
    ids = doc._school_ids
    for element in elements:
        for pr in element.iter(DOC_PR):  # معرّفات الأشكال فريدة في الوثيقة حين يتكرر الغلاف لكل نموذج
            pr.set("id", str(next(ids)))
    fill(elements, cover_values(header, paper, duration))
    for element in elements:
        if element.tag == qn("w:tbl") and "رقم السؤال" in "".join(element.itertext()):
            _score_rows(element, paper)
    anchor = body[-1]
    for element in elements:
        anchor.addprevious(element)


# ---------- الأسئلة ----------


def _instruction(doc, text: str) -> None:
    table = x.make_table(doc, 1, [2.2, CONTENT_CM - 2.6], borders=None, align="right")
    x.set_row(table.rows[0])
    label, body = table.cell(0, 0), table.cell(0, 1)
    x.set_cell(label, 2.2, shade=HEAD)
    x.add_text(x.new_paragraph(label, align="center", after=0), "تعليمات", size=12, bold=True)
    x.set_cell(body, CONTENT_CM - 2.6)
    x.add_text(x.new_paragraph(body, after=0), text, size=11, bold=True)
    x.spacer(doc, 6)


def _head(table, question: dict, widths: list[float]) -> None:
    row = table.rows[0]
    x.set_row(row, header=False)
    x.keep_row_with_next(row)
    texts = (f"السؤال رقم ({question['number']})", "", f"الدرجة ( {question['marks']} )")
    for cell, width, text in zip(row.cells, widths, texts, strict=True):
        x.set_cell(cell, width, shade=HEAD, borders=x.box(6, x.INK, inside=False))
        align = "left" if text.startswith("الدرجة") else None
        par = x.new_paragraph(cell, align=align, after=0, keep_next=True)
        if text:
            x.add_text(par, text, size=10, bold=True)


def _option(cell, index: int, part: dict, width: float, keep: bool) -> None:
    """صف بديل: الحرف في مربع صغير ثم القيمة، من اليسار إلى اليمين كما في القالب."""
    inner = x.make_table(
        cell, 1, [0.6, width - 0.6], rtl=False, borders=None, align="left", cell_margin_cm=0.08
    )
    x.set_row(inner.rows[0])
    letter, value = inner.cell(0, 0), inner.cell(0, 1)
    x.set_cell(letter, 0.6, borders=x.box(6, x.INK, inside=False))
    x.add_text(
        x.new_paragraph(letter, rtl=False, align="center", after=0, keep_next=keep), LETTERS[index], size=9
    )
    x.set_cell(value, width - 0.6)
    par = x.new_paragraph(value, rtl=False, align="left", after=0, keep_next=keep, indent_cm=0.2)
    # فقرة فيها معادلة وحدها يعرضها Word معادلة مستقلة في الوسط؛ المسافة قبلها تبقيها في السطر عند اليسار
    x.add_text(par, " ", size=11)
    graphs = part.get("option_graphs") or []
    if graphs and index < len(graphs):
        png, w, h = render_graph(graphs[index], compact=True)
        scale = min(1.0, 3.6 / (h / 96 * 2.54))
        x.add_picture(par, png, w / 96 * 2.54 * scale)
    else:
        from ..builder import rich

        rich(value, part["options"][index], size=11, rtl=False, first=par, keep_next=keep)


def _options(cell, part: dict, width: float, keep: bool) -> None:
    from ..builder import SHORT_OPTION

    options = part["options"]
    columns = 1  # البدائل عمودية كما في القالب
    _ = SHORT_OPTION
    rows = (len(options) + columns - 1) // columns
    col = (width - 0.4) / columns
    grid = x.make_table(
        cell, rows, [col] * columns, rtl=False, borders=None, align="left", cell_margin_cm=0.05
    )
    for r in range(rows):
        x.set_row(grid.rows[r], height_cm=0.8)
        for c in range(columns):
            index = r * columns + c if columns == 2 else r
            target = grid.cell(r, c)
            x.set_cell(target, col)
            if index < len(options):
                _option(target, index, part, col - 0.1, keep or r < rows - 1)


def _work_box(cell, part: dict, width: float) -> None:
    x.add_text(
        x.new_paragraph(cell, before=4, after=2, keep_next=True),
        "وضح خطوات الحل في المستطيل أدناه",
        size=9.5,
        bold=True,
    )
    height_cm = min(max(60 + part["marks"] * 45, 96), 300) / 96 * 2.54
    box = x.make_table(cell, 1, [width - 0.6], borders=x.box(8, x.INK, inside=False))
    x.set_row(box.rows[0], height_cm=height_cm)
    x.set_cell(box.cell(0, 0), width - 0.6, borders=x.box(8, x.INK, inside=False), valign="top")
    x.new_paragraph(box.cell(0, 0), after=0)


def question(doc, item: dict) -> None:
    from ..builder import graph_picture, rich

    widths = [6.0, CONTENT_CM - 9.6, 3.6]
    table = x.make_table(doc, 2, widths, borders=x.box(6, x.INK, inside=False))
    _head(table, item, widths)
    body_row = table.rows[1]
    mcq = item["kind"] == "mcq"
    x.set_row(body_row, cant_split=mcq)
    first = body_row.cells[0]
    merged = first.merge(body_row.cells[-1])
    x.set_cell(merged, CONTENT_CM, span=3, valign="top", borders=x.box(6, x.INK, inside=False))
    inner = CONTENT_CM - 0.4
    for part in item["parts"]:
        stem = x.new_paragraph(merged, before=4, after=4, keep_next=True)
        label = part.get("label") or ""
        if label:
            x.add_text(stem, f"{label}.{x.RLM} ", size=11, bold=True, force_rtl=True)
        rich(merged, part["stem"], size=11, bold=True, first=stem, keep_next=True)
        if part.get("graph"):
            graph_picture(merged, part["graph"], compact=True, align="right")
        if part["options"]:
            _options(merged, part, inner, keep=False)
        else:
            _work_box(merged, part, inner)
    x.spacer(merged, 2)
    x.spacer(doc, 8)


def exam_sheet(doc, paper: dict, header: dict, duration: str, *, first: bool) -> None:
    """غلاف النموذج ثم أسئلته في قسم واحد بترقيم يبدأ من 1 وتذييل «صفحة n من N»."""
    if not first:
        doc.add_section(WD_SECTION.NEW_PAGE)
    section = doc.sections[-1]
    _footer(section)
    cover(doc, header, paper, duration)
    questions = paper["questions"]
    mcq = [q for q in questions if q["kind"] == "mcq"]
    essay = [q for q in questions if q["kind"] != "mcq"]
    x.spacer(doc, 1, page_break=True)
    if mcq:
        _instruction(
            doc,
            f"اختر الإجابة الصحيحة لكل من الأسئلة من {mcq[0]['number']} إلى {mcq[-1]['number']}،"
            " وذلك بوضع علامة × داخل المربع المجاور للإجابة الصحيحة:",
        )
        for item in mcq:
            question(doc, item)
        if essay:
            x.add_text(
                x.new_paragraph(doc, align="center", after=0), "انتهى الجزء الأول من الاختبار", size=10.5
            )
            x.spacer(doc, 1, page_break=True)
    if essay:
        _instruction(
            doc,
            f"عند الإجابة على الأسئلة من {essay[0]['number']} إلى {essay[-1]['number']}،"
            " اكتب إجاباتك في المساحات المخصصة لذلك مع توضيح خطوات الحل:",
        )
        for item in essay:
            question(doc, item)
    x.add_text(
        x.new_paragraph(doc, align="center", before=6, after=0), "انتهت الأسئلة نرجو لكم التوفيق", size=11
    )


def _footer(section) -> None:
    """تذييل القالب: خط علوي و«صفحة n من N» للنموذج وحده (الترقيم يبدأ مع كل قسم)."""
    sect_pr = section._sectPr
    for old in sect_pr.findall(qn("w:pgNumType")):
        sect_pr.remove(old)
    sect_pr.append(parse_xml(f'<w:pgNumType {x.W} w:start="1"/>'))
    section.footer.is_linked_to_previous = False
    footer = section.footer
    for child in list(footer._element):  # تذييل القالب (حقول داخل معادلة ومربعات نص) يُستبدل كله
        footer._element.remove(child)
    section.footer_distance = Cm(0.6)
    par = x.new_paragraph(footer, align="left", after=0, line=None, top=("single", 6, x.INK))
    x.add_text(par, "صفحة ", size=9, bold=True)
    x.add_field(par, " PAGE ", size=9, bold=True)
    x.add_text(par, " من ", size=9, bold=True)
    x.add_field(par, " SECTIONPAGES ", size=9, bold=True)
