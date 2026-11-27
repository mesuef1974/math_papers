"""الاختبار وورقة العمل في Word بقالب المدرسة (قرار المالك 2026-11-18): خيار إضافي بجانب إخراج «أوراق».

الغلاف مأخوذ كما هو من ملف قالب المدرسة (`assets/school/cover.docx`: شعار الوزارة والمثلث وجدول الرصد والتعليمات،
مجرّدًا من الأسئلة، وحقوله رموز مثل {school} تُملأ من الورقة). الأسئلة تُبنى بنسق القالب: كل سؤال إطار بشريط رمادي
«السؤال رقم (n) | الدرجة (m)»، والبدائل عمودية بحرف في مربع، والمقالي مستطيل «وضح خطوات الحل»، والتذييل «صفحة n من N»
لكل نموذج. المحتوى (النص والمعادلات OMML والرسوم) هو نفسه في إخراج «أوراق».

ورقة العمل (وكل ورقة في حزمة) تأخذ من الغلاف ترويسته وحدها: شعار الوزارة والمثلث وحقول الطالب واسم المدرسة
والعنوان والمادة (والعام إن كان في العنوان)، بلا مربع المجموع ولا الزمن ولا جدول الرصد ولا تعليمات الاختبار،
ثم أسئلتها في الصفحة نفسها بالأطر، وخانة الدرجة في الشريط فارغة لأن أسئلتها بلا درجات.
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
    # عنوان الاختبار قبل النقطتين (ما بعدها نطاقه وعامه)، وعنوان ورقة العمل كله «ورقة عمل: الدرس»
    exam = title.split(":")[0].strip() if paper["kind"] == "exam" else title.strip()
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


# ما يُسقط من الغلاف في ورقة العمل: فقرتا مربع المجموع والزمن، وجدول الرصد وكل ما بعده
WORKSHEET_DROP = ("{total}", "{minutes}")
SCORE_TABLE = "رقم السؤال"


def _header_only(elements: list, values: dict[str, str]) -> list:
    kept = []
    for element in elements:
        text = "".join(element.itertext())
        if element.tag == qn("w:tbl") and SCORE_TABLE in text:
            break
        if any(key in text for key in WORKSHEET_DROP) or ("{year}" in text and not values["{year}"]):
            continue
        kept.append(element)
    return kept


def cover(doc, header: dict, paper: dict, duration: str, *, full: bool = True, prefix: str = "") -> None:
    """الغلاف كاملًا للاختبار، أو ترويسته وحدها (full=False) لورقة العمل وللمفتاح المستقل (prefix قبل العنوان)."""
    body = doc.element.body
    values = cover_values(header, paper, duration)
    if prefix:
        values["{exam}"] = f"{prefix}: {values['{exam}']}"
    elements = [copy.deepcopy(element) for element in doc._school_cover]
    if not full:
        elements = _header_only(elements, values)
    ids = doc._school_ids
    for element in elements:
        for pr in element.iter(DOC_PR):  # معرّفات الأشكال فريدة في الوثيقة حين يتكرر الغلاف لكل نموذج
            pr.set("id", str(next(ids)))
    fill(elements, values)
    for element in elements:
        if element.tag == qn("w:tbl") and "رقم السؤال" in "".join(element.itertext()):
            _score_rows(element, paper)
    anchor = body[-1]
    for element in elements:
        anchor.addprevious(element)


# ---------- الأسئلة ----------


def _instruction(doc, text: str) -> None:
    """مربع التعليمات يلحق بالسؤال الذي بعده (keepNext في صفه وفي الفاصل)، فلا تبقى تعليمات المقالي وحدها في صفحة
    والسؤال 11 في التي تليها؛ وشريط السؤال يلحق بصف جزئه الأول، فالسلسلة تصل إلى نص السؤال."""
    table = x.make_table(doc, 1, [2.2, CONTENT_CM - 2.6], borders=None, align="right")
    x.set_row(table.rows[0])
    label, body = table.cell(0, 0), table.cell(0, 1)
    x.set_cell(label, 2.2, shade=HEAD)
    x.add_text(x.new_paragraph(label, align="center", after=0), "تعليمات", size=12, bold=True)
    x.set_cell(body, CONTENT_CM - 2.6)
    x.add_text(x.new_paragraph(body, after=0), text, size=11, bold=True)
    x.keep_row_with_next(table.rows[0])
    x.spacer(doc, 6, keep_next=True)


def _head(table, question: dict, widths: list[float]) -> None:
    """شريط السؤال سطر واحد: فقرة واحدة في كل خلية. keepNext يُضاف بعد ملء الخلايا، فإضافته قبلها كانت تُبقي
    الفقرة الفارغة الأولى في الخلية (لا تُعاد استعمالها) فيصير الشريط سطرين."""
    row = table.rows[0]
    x.set_row(row, header=False)
    # سؤال ورقة العمل بلا درجة: الخانة تبقى فارغة في الشريط
    grade = f"الدرجة ( {question['marks']} )" if question["marks"] else ""
    texts = (f"السؤال رقم ({question['number']})", "", grade)
    for cell, width, text in zip(row.cells, widths, texts, strict=True):
        x.set_cell(cell, width, shade=HEAD, borders=x.box(6, x.INK, inside=False))
        align = "left" if text.startswith("الدرجة") else None
        par = x.new_paragraph(cell, align=align, before=1, after=1, keep_next=True)
        if text:
            x.add_text(par, text, size=10.5, bold=True)
    x.keep_row_with_next(row)


MATH = re.compile(r"\$[^$]*\$")
TINY = '<w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/>'


def arabic_option(text: str) -> bool:
    """بديل فيه كلام عربي خارج المعادلات («$4$ ساعات») فقرته عربية الاتجاه؛ في فقرة لاتينية يُقرأ «ساعات 4»."""
    return bool(x.ARABIC.search(MATH.sub("", text)))


def _nested(cell, table) -> None:
    """python-docx يضع الجدول المتداخل بين فقرتين فارغتين (فقرة الخلية الأولى والفقرة التي يشترطها Word بعده)،
    فكان كل بديل ثلاثة أسطر وإطار السؤال الموضوعي نصف صفحة. الأولى تُحذف (الخلية تبدأ بجدول) والأخيرة نقطة واحدة."""
    before = table._tbl.getprevious()
    if before is not None and _blank(before) and len(before) <= 1:
        cell._tc.remove(before)
    after = table._tbl.getnext()
    if after is not None and after.tag == qn("w:p"):
        for ppr in after.findall(qn("w:pPr")):
            after.remove(ppr)
        after.insert(0, parse_xml(f"<w:pPr {x.W}>{TINY}</w:pPr>"))


def _option(cell, index: int, part: dict, width: float, keep: bool) -> None:
    """صف بديل: الحرف في مربع صغير ثم القيمة، من اليسار إلى اليمين كما في القالب. القيمة العربية فقرة عربية
    الاتجاه محاذاتها يسار، فتلاصق المربع."""
    inner = x.make_table(
        cell, 1, [0.6, width - 0.6], rtl=False, borders=None, align="left", cell_margin_cm=0.08
    )
    _nested(cell, inner)
    x.set_row(inner.rows[0])
    letter, value = inner.cell(0, 0), inner.cell(0, 1)
    x.set_cell(letter, 0.6, borders=x.box(6, x.INK, inside=False))
    x.add_text(
        x.new_paragraph(letter, rtl=False, align="center", after=0, keep_next=keep), LETTERS[index], size=9
    )
    x.set_cell(value, width - 0.6)
    graphs = part.get("option_graphs") or []
    rtl = not (graphs and index < len(graphs)) and arabic_option(part["options"][index])
    # w:ind start في الفقرة العربية طرفها الأيمن، فالإزاحة عن المربع للاتينية وحدها
    par = x.new_paragraph(value, rtl=rtl, align="left", after=0, keep_next=keep, indent_cm=0 if rtl else 0.2)
    # فقرة فيها معادلة وحدها يعرضها Word معادلة مستقلة في الوسط؛ المسافة قبلها تبقيها في السطر عند اليسار
    x.add_text(par, " ", size=11)
    if graphs and index < len(graphs):
        png, w, h = render_graph(graphs[index], compact=True)
        scale = min(1.0, 3.6 / (h / 96 * 2.54))
        x.add_picture(par, png, w / 96 * 2.54 * scale)
    else:
        from ..builder import rich

        rich(value, part["options"][index], size=11, rtl=rtl, first=par, keep_next=keep)


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
    _nested(cell, grid)
    for r in range(rows):
        x.set_row(grid.rows[r], height_cm=0.7)
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
    _nested(cell, box)
    x.set_row(box.rows[0], height_cm=height_cm)
    x.set_cell(box.cell(0, 0), width - 0.6, borders=x.box(8, x.INK, inside=False), valign="top")
    x.new_paragraph(box.cell(0, 0), after=0)


def question(doc, item: dict) -> None:
    """إطار السؤال: الشريط ثم صف لكل جزء. صف الجزء لا ينقسم بين صفحتين (نصه مع بدائله أو مستطيل حله)، والشريط
    يلحق بصف الجزء الأول. السؤال الذي تتسع له صفحة يلحق كل صف فيه عدا الأخير بما بعده، فيبقى كله في صفحة ومعه
    مربع التعليمات قبله. والأطول من صفحة (مقاليات الثاني عشر) تُنزع keepNext من صفوف أجزائه كلها: Word يربط الصف
    بما بعده إن كانت فيه فقرة واحدة تلحق بالتالي، فكان يعامل السؤال كتلة أطول من صفحة فيدفعه إلى صفحة جديدة
    ويترك التعليمات وحدها؛ فينقسم بين فروعه لا داخلها (قرار المالك 2026-11-19، مقيس في Word)."""
    from ..builder import graph_picture, rich, spotting_steps

    widths = [6.0, CONTENT_CM - 9.6, 3.6]
    parts = item["parts"]
    table = x.make_table(doc, 1 + len(parts), widths, borders=x.box(6, x.INK, inside=False))
    _head(table, item, widths)
    inner = CONTENT_CM - 0.4
    for index, part in enumerate(parts, start=1):
        row = table.rows[index]
        x.set_row(row, cant_split=True)
        merged = row.cells[0].merge(row.cells[-1])
        x.set_cell(merged, CONTENT_CM, span=3, valign="top", borders=x.box(6, x.INK, inside=False))
        stem = x.new_paragraph(merged, before=4, after=4, keep_next=True)
        label = part.get("label") or ""
        if label:
            x.add_text(stem, f"{label}.{x.RLM} ", size=11, bold=True, force_rtl=True)
        rich(merged, part["stem"], size=11, bold=True, first=stem, keep_next=True)
        if part.get("graph"):
            graph_picture(merged, part["graph"], compact=True, align="right")
        if part.get("spotting"):
            spotting_steps(merged, part)
        if part["options"]:
            _options(merged, part, inner, keep=False)
        else:
            _work_box(merged, part, inner)
        x.spacer(merged, 2)
    if sum(_row_height_cm(row) for row in table.rows) <= PAGE_FIT_CM:
        for row in table.rows[:-1]:
            x.keep_row_with_next(row)
    else:
        for row in table.rows[1:]:
            _release_row(row)
    x.spacer(doc, 8)


# ارتفاع ما يتسع له متن الصفحة تحت هوامش القالب وتذييله، بهامش أمان؛ التقدير يزيد ولا ينقص فيُقسَم السؤال المشكوك فيه
PAGE_FIT_CM = 24.0
TEXT_LINE_CM = 0.6


def _row_height_cm(row) -> float:
    """تقدير زائد لارتفاع صف: الصور بامتدادها، والصفوف المتداخلة (مستطيل الحل والبدائل) بارتفاعها، وسطر لكل فقرة نص."""
    tr = row._tr
    pictures = sum(int(e.get("cy")) for e in tr.iter(qn("wp:extent"))) / 360000
    rows = sum(int(h.get(qn("w:val"))) for h in tr.iter(qn("w:trHeight"))) / 567
    lines = sum(1 for p in tr.iter(qn("w:p")) if "".join(p.itertext()).strip()) * TEXT_LINE_CM
    return pictures + rows + lines


def _release_row(row) -> None:
    """صف جزء لا يلحق بما بعده: يُنزع keepNext من كل فقرة فيه (الصف cantSplit فلا تنفصل أجزاؤه بدونه)."""
    for keep in list(row._tr.iter(qn("w:keepNext"))):
        keep.getparent().remove(keep)


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
    x.add_text(x.new_paragraph(doc, align="center", before=6, after=0), CLOSING, size=11)


CLOSING = "انتهت الأسئلة نرجو لكم التوفيق"
WORKSHEET_INSTRUCTION = "أجب عن الأسئلة الآتية، ووضح خطوات الحل في المستطيل المخصص لكل سؤال:"


def worksheet_sheet(doc, paper: dict, header: dict, *, first: bool, last: bool = True) -> None:
    """ورقة العمل: ترويسة القالب ثم تعليمتها وأسئلتها في الصفحة نفسها، بقسم وترقيم «صفحة n من N» لكل ورقة.
    عبارة الختام بعد آخر ورقة وحدها (last)، فلا تتكرر في آخر كل ورقة من الحزمة."""
    if not first:
        doc.add_section(WD_SECTION.NEW_PAGE)
    _footer(doc.sections[-1])
    cover(doc, header, paper, "", full=False)
    x.spacer(doc, 6)
    _instruction(doc, header["instructions"] or WORKSHEET_INSTRUCTION)
    for item in paper["questions"]:
        question(doc, item)
    if last:
        x.add_text(x.new_paragraph(doc, align="center", before=6, after=0), CLOSING, size=11)


def key_header(doc, paper: dict, header: dict, label: str, *, first: bool) -> None:
    """ترويسة المفتاح المستقل: قسم بترقيمه لكل نموذج أو ورقة، وترويسة القالب وحدها بعنوان «<label>: <العنوان>»."""
    if not first:
        doc.add_section(WD_SECTION.NEW_PAGE)
    _footer(doc.sections[-1])
    cover(doc, header, paper, "", full=False, prefix=label)
    x.spacer(doc, 6)


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
