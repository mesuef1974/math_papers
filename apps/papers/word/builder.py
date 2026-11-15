"""ورقة Word بتخطيط الورقة المطبوعة: ترويسة أو غلاف كراسة، أسئلة بخيارات A–D، صناديق حل، جدول رصد، مفتاح.

يستقبل الحمولة نفسها التي يطبعها PDF (PdfIn.dict)، فما في الشاشة والـPDF هو ما في الملف. المعادلات OMML أصلية
قابلة للتحرير في Word، والرسوم صور PNG، والجداول جداول Word حقيقية بحدود وعرض ثابت.
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Cm, Pt

from . import ooxml as x
from .graph_png import render_graph
from .omml import split_array, to_omml

W = nsdecls("w")
CONTENT_CM = 17.8
OPTION_LABELS = "ABCD"
LEVEL_NAMES = {"K": "سهل", "A": "متوسط", "R": "مهارات عليا"}
FORM_LABELS = {"A": "أ", "B": "ب"}
DOTS = "." * 20
NBSP = "\u00a0"
QUIZ_MINUTES = 20
SHORT_OPTION = 26
MAX_GRAPH_HEIGHT_CM = 6.2
FOOTER_LOGO_CM = 1.9  # عرض الشعار المقفل في التذييل (ارتفاعه نحو 0.8 سم): أكبر من الكلمة الحية 8.5pt ويبقى داخل هامش التذييل
BUNDLE_COVER_TITLE = "حزمة أوراق العمل: كل دروس الفصل الأول"
LOGO = (Path(__file__).parent / "assets" / "lockup.png").read_bytes()
# شريط النمط (patterns/motif-soft.svg) بعرض المحتوى؛ تحويل نقطي بدقة 300dpi وخلفية شفافة، يُحدَّث مع كل إصدار من سِمة
PATTERN_BAND = (Path(__file__).parent / "assets" / "pattern_band.png").read_bytes()
HEADER_CM = [3.0, 10.6, 4.2]  # الشعار، العنوان، المدرسة والمعلم
SIDE_GRAPH_CM = 5.4
LINE_CM = 0.8
COVER_NOTES = [
    "هذا الاختبار للتدريب ولا يغطي جميع موضوعات الفصل.",
    "الاختبار لا يغني عن الكتاب المدرسي ولا عن الخطة الفصلية.",
]


# ---------- نصوص مساعدة ----------


def marks_label(marks: int) -> str:
    if marks == 1:
        return "درجة واحدة"
    if marks == 2:
        return "درجتان"
    if 3 <= marks <= 10:
        return f"{marks} درجات"
    return f"{marks} درجة"


def duration_label(minutes: int | None) -> str:
    if not minutes:
        return ""
    named = {
        30: "نصف ساعة",
        45: "ثلاثة أرباع الساعة",
        60: "ساعة",
        90: "ساعة ونصف",
        120: "ساعتان",
        150: "ساعتان ونصف",
        180: "ثلاث ساعات",
    }
    return named.get(minutes, f"{minutes} دقيقة")


def split_math(text: str) -> list[tuple[bool, bool, str]]:
    """(رياضة؟، معروضة؟، قيمة): $...$ سطري و$$...$$ معروض و\\$ دولار حرفي، وغير المغلق يبقى نصًا."""
    out: list[tuple[bool, bool, str]] = []
    buffer = ""
    i = 0
    while i < len(text):
        if text[i] == "\\" and text[i + 1 : i + 2] == "$":
            buffer += "$"
            i += 2
            continue
        if text[i] == "$":
            display = text[i + 1 : i + 2] == "$"
            fence = "$$" if display else "$"
            close = text.find(fence, i + len(fence))
            if close == -1:
                buffer += text[i:]
                break
            if buffer:
                out.append((False, False, buffer))
                buffer = ""
            out.append((True, display, text[i + len(fence) : close]))
            i = close + len(fence)
            continue
        buffer += text[i]
        i += 1
    if buffer:
        out.append((False, False, buffer))
    return out


def header_of(paper: dict, profile: dict, date: str, section: str, multi: bool) -> dict:
    kind = paper["kind"]
    minutes = profile["exam_minutes"] if kind == "exam" else QUIZ_MINUTES if kind == "quiz" else None
    instructions = profile["worksheet_instructions"] if kind == "worksheet" else profile["exam_instructions"]
    return {
        "school": profile.get("school", ""),
        "teacher": profile.get("teacher_name", ""),
        "subject": profile["subject"],
        "grade": profile.get("grade", ""),
        "title": paper["title"],
        "minutes": minutes,
        "date": date,
        "section": section,
        "total": paper["total_marks"],
        "instructions": instructions,
        "form": FORM_LABELS.get(paper.get("form", "A"), "") if multi else "",
    }


def labelled(paragraph, text: str, **fmt) -> None:
    """«تسمية: قيمة» بتشغيلين: القيمة اللاتينية (12/3) في تشغيل غير عربي، فلا يقلب Word طرفي الشرطة."""
    label, separator, value = text.partition(": ")
    x.add_text(paragraph, label + separator, **fmt)
    x.add_text(paragraph, value, **fmt)


def short_grade(grade: str) -> str:
    return re.sub(r"^الصف\s+", "", grade)


# ---------- نص غني: عربي ورياضيات ----------


def rich(container, text: str, *, size: float = 11, bold: bool = False, rtl: bool = True, first=None, **par):
    """يكتب نصًا فيه $...$ في فقرة (أو أكثر عند مصفوفة/معادلة معروضة). first: فقرة جاهزة تُكمَل. يعيد آخر فقرة."""
    paragraph = first if first is not None else x.new_paragraph(container, rtl=rtl, **par)
    fmt = {"size": size, "bold": bold}
    for is_math, display, value in split_math(text):
        if not is_math:
            x.add_text(paragraph, value, **fmt)
            continue
        found = split_array(value)
        if found:
            before, table, after = found
            if before.strip():
                x.add_math(paragraph, before)
            value_table(container, table)
            paragraph = x.new_paragraph(container, rtl=rtl, **par)
            if after.strip():
                x.add_math(paragraph, after)
        elif display:
            if len(paragraph._p) > 1:  # فيها ما قبلها
                paragraph = x.new_paragraph(container, rtl=rtl, **{**par, "keep_next": True})
            paragraph = x.new_paragraph(
                container, rtl=rtl, align="center", **{k: v for k, v in par.items() if k != "align"}
            )
            x.add_math(paragraph, value)
            paragraph = x.new_paragraph(container, rtl=rtl, **par)
        else:
            x.add_math(paragraph, value)
    return paragraph


def value_table(container, table) -> None:
    """مصفوفة LaTeX (جدول قيم) → جدول Word باتجاه LTR: عمود العناوين يفصله خط عمودي."""
    cols = max(len(row) for row in table.rows)
    letters = [c for c in table.spec if c in "clr"]
    widths = [2.2] + [1.7] * (cols - 1)
    word = x.make_table(container, len(table.rows), widths, rtl=False, borders=x.box(6, x.INK, inside=False))
    for r, (row, rule) in enumerate(zip(table.rows, table.rules_above, strict=True)):
        x.set_row(word.rows[r], height_cm=0.75)
        for c in range(cols):
            cell = word.cell(r, c)
            edges: dict[str, Any] = {}
            if rule and r:
                edges["top"] = x.BORDER
            if c == 0 and cols > 1:
                edges["right"] = x.BORDER
            x.set_cell(cell, widths[c], borders=edges or None)
            par = x.new_paragraph(cell, rtl=False, align="center", after=0, line=None)
            if c < len(row):
                x.add_math(par, row[c])
    x.spacer(container, 4)
    _ = letters


# ---------- الرسوم ----------


def graph_picture(
    container, graph: dict, compact: bool, *, align: str = "center", cap_cm: float = MAX_GRAPH_HEIGHT_CM
):
    png, width, height = render_graph(graph, compact=compact)
    width_cm, height_cm = width / 96 * 2.54, height / 96 * 2.54
    scale = min(1.0, cap_cm / height_cm)
    paragraph = x.new_paragraph(
        container, rtl=False, align=align, before=2, after=2, line=None, keep_next=True
    )
    x.add_picture(paragraph, png, width_cm * scale)
    return paragraph


# ---------- الترويسة والغلاف ----------


def paper_header(doc, header: dict, *, compact: bool = False, page_break: bool = False) -> None:
    if page_break:
        x.spacer(doc, 1, page_break=True)
    top = x.make_table(doc, 1, HEADER_CM, borders=None)
    x.set_row(top.rows[0])
    brand = top.cell(0, 0)
    x.set_cell(brand, HEADER_CM[0])
    x.add_picture(
        x.new_paragraph(brand, rtl=False, align="right", after=0, line=None), LOGO, 2.3 if compact else 2.7
    )
    mid = top.cell(0, 1)
    x.set_cell(mid, HEADER_CM[1])
    # العنوان الطويل (مفتاح اختبار درسين) يصغر قليلًا ليبقى في سطر واحد ما أمكن
    title_size = 14 if len(header["title"]) <= 46 else 12
    x.add_text(
        x.new_paragraph(mid, align="center", after=0),
        header["title"],
        size=title_size,
        bold=True,
        color=x.BRAND_STRONG,
    )
    org = top.cell(0, 2)
    x.set_cell(org, HEADER_CM[2])
    first = True
    if header["school"]:
        x.add_text(x.new_paragraph(org, align="left", after=0), header["school"], size=10, bold=True)
        first = False
    if header["teacher"]:
        x.add_text(x.new_paragraph(org, align="left", after=0), f"المعلم: {header['teacher']}", size=9.5)
        first = False
    if first:
        x.new_paragraph(org, after=0)
    x.spacer(doc, 4)

    items = [("المادة", header["subject"])]
    if header["grade"]:
        items.append(("الصف", short_grade(header["grade"])))
    if header["form"]:
        items.append(("النموذج", header["form"]))
    if header["minutes"]:
        items.append(("زمن الاختبار", duration_label(header["minutes"])))
    if header["total"]:
        items.append(("الدرجة الكلية", f"{header['total']} درجة"))
    if header["date"]:
        items.append(("التاريخ", header["date"]))
    weights = [max(len(label), len(value)) + 6 for label, value in items]
    meta_widths = [CONTENT_CM * weight / sum(weights) for weight in weights]
    meta = x.make_table(doc, 1, meta_widths, borders=x.box(6, x.LINE))
    x.set_row(meta.rows[0])
    for index, (label, value) in enumerate(items):
        cell = meta.cell(0, index)
        x.set_cell(cell, meta_widths[index], borders=None)
        x.add_text(x.new_paragraph(cell, align="center", after=0), label, size=8.5, color=x.BRAND_STRONG)
        x.add_text(x.new_paragraph(cell, align="center", after=0), value, size=10.5, bold=True)
    if not compact:
        student = x.make_table(doc, 1, [9.0, 4.4, 4.4], borders=None)
        cells = [
            f"اسم الطالب: {DOTS}{DOTS}",
            f"الشعبة: {header['section'] or DOTS}",
            f"الدرجة: ........ / {header['total']}" if header["total"] else "",
        ]
        for index, (cell, text, w) in enumerate(
            zip(student.rows[0].cells, cells, [9.0, 4.4, 4.4], strict=True)
        ):
            x.set_cell(cell, w)
            labelled(x.new_paragraph(cell, before=6, after=2), text, size=10.5)
            _ = index
        if header["instructions"]:
            par = x.new_paragraph(doc, before=2, after=2)
            x.add_text(par, "تعليمات: ", size=10, bold=True, color=x.BRAND_STRONG)
            x.add_text(par, header["instructions"], size=10)
    x.new_paragraph(doc, before=0, after=6, line=None, exact_pt=2, bottom=("single", 20, x.BRAND))


def accent_bar(doc, width_cm: float = 2.6) -> None:
    """شريط ذهبي قصير في الوسط: تزيين الهوية تحت عنوان الغلاف."""
    bar = x.make_table(doc, 1, [width_cm], borders={"top": {"val": "single", "sz": 36, "color": x.ACCENT}})
    x.set_row(bar.rows[0])
    x.new_paragraph(bar.cell(0, 0), after=0, line=None, exact_pt=4)
    x.spacer(doc, 4)


def cover_page(doc, header: dict, paper: dict) -> None:
    """غلاف كراسة الاختبار ثم صفحة التعليمات الثنائية على نسق كراسات الوزارة."""
    x.add_picture(
        x.new_paragraph(doc, rtl=False, align="center", after=10, line=None), PATTERN_BAND, CONTENT_CM
    )
    x.add_picture(x.new_paragraph(doc, rtl=False, align="center", after=14, line=None), LOGO, 4.4)
    for text, size, bold, gap in (
        (header["school"], 15, True, 2),
        (f"المعلم: {header['teacher']}" if header["teacher"] else "", 11, False, 24),
    ):
        if text:
            x.add_text(x.new_paragraph(doc, align="center", after=gap), text, size=size, bold=bold)
    title = f"اختبار {header['subject']}" + (" (تدريبي)" if paper.get("is_forecast") else "")
    x.add_text(
        x.new_paragraph(doc, align="center", before=18, after=10),
        title,
        size=26,
        bold=True,
        color=x.BRAND_STRONG,
    )
    accent_bar(doc)
    x.add_text(x.new_paragraph(doc, align="center", after=4), header["title"], size=15)
    if header["grade"]:
        x.add_text(x.new_paragraph(doc, align="center", after=4), header["grade"], size=13)
    if header["form"]:
        x.add_text(
            x.new_paragraph(doc, align="center", after=4), f"النموذج {header['form']}", size=13, bold=True
        )
    x.spacer(doc, 14)
    facts = []
    if header["minutes"]:
        facts.append(("زمن الاختبار", duration_label(header["minutes"])))
    facts.append(("الدرجة الكلية", f"{header['total']} درجة"))
    if header["date"]:
        facts.append(("التاريخ", header["date"]))
    width = 4.6
    table = x.make_table(doc, 1, [width] * len(facts), borders=x.box(8, x.BRAND))
    for index, (label, value) in enumerate(facts):
        cell = table.cell(0, index)
        x.set_cell(cell, width, shade=x.SHADE)
        x.add_text(
            x.new_paragraph(cell, align="center", before=4, after=0), label, size=10, color=x.BRAND_STRONG
        )
        x.add_text(x.new_paragraph(cell, align="center", after=4), value, size=13, bold=True)
    x.spacer(doc, 26)
    x.add_text(x.new_paragraph(doc, after=14), f"اسم الطالب: {'.' * 40}", size=13)
    labelled(x.new_paragraph(doc, after=14), f"الشعبة: {header['section'] or '.' * 16}", size=13)
    x.spacer(doc, 16)
    notes = x.make_table(doc, 1, [CONTENT_CM], borders=x.box(8, x.LINE))
    cell = notes.cell(0, 0)
    x.set_cell(cell, CONTENT_CM)
    x.add_text(x.new_paragraph(cell, before=3, after=2), "ملاحظات:", size=11, bold=True)
    for note in COVER_NOTES:
        x.add_text(x.new_paragraph(cell, after=2, indent_cm=0.4), f"• {note}", size=10.5)
    instructions_page(doc, header, paper)


def instructions_page(doc, header: dict, paper: dict) -> None:
    questions = paper["questions"]
    mcq = sum(1 for q in questions if q["kind"] == "mcq")
    essay = len(questions) - mcq
    minutes = header["minutes"]
    rules = [
        (
            f"عدد الأسئلة {len(questions)}: {mcq} موضوعية و{essay} مقالية، والدرجة الكلية {header['total']}.",
            f"{len(questions)} items: {mcq} multiple-choice and {essay} constructed-response, {header['total']} marks in total.",
        ),
        (
            f"زمن الاختبار {duration_label(minutes)}." if minutes else "",
            f"Testing time: {minutes} minutes." if minutes else "",
        ),
        (
            "أجب بقلم أزرق أو أسود، واستعمل قلم الرصاص للرسوم فقط.",
            "Answer in blue or black ink; use a pencil for drawings only.",
        ),
        (
            "في الأسئلة الموضوعية ضع علامة × في المربع المجاور للإجابة الصحيحة، ولا تختر أكثر من إجابة واحدة.",
            "For multiple-choice items, mark × in the box beside the correct answer; choose one answer only.",
        ),
        (
            "لتغيير إجابتك املأ المربع الذي اخترته أولًا، ثم ضع × في المربع الجديد.",
            "To change an answer, fill in the box you marked first, then mark × in the new box.",
        ),
        (
            "في الأسئلة المقالية اكتب الحل في الفراغ المخصص موضحًا خطواته؛ ما يُكتب خارجه لا يُصحَّح.",
            "For constructed-response items, write your solution with its steps in the space provided; work outside it is not marked.",
        ),
        ("الآلة الحاسبة العلمية غير البيانية مسموح بها.", "A non-graphing scientific calculator is allowed."),
        (
            "لا تقضِ وقتًا طويلًا في سؤال واحد؛ انتقل إلى غيره ثم عد إليه.",
            "Do not spend too long on one item; move on and come back to it.",
        ),
    ]
    rules = [rule for rule in rules if rule[0]]
    x.spacer(doc, 1, page_break=True)
    head = x.make_table(doc, 1, [8.9, 8.9], borders={"bottom": x.BRAND_EDGE})
    x.set_row(head.rows[0])
    x.set_cell(head.cell(0, 0), 8.9)
    x.add_text(
        x.new_paragraph(head.cell(0, 0), before=0, after=2),
        "تعليمات عامة",
        size=15,
        bold=True,
        color=x.BRAND_STRONG,
    )
    x.set_cell(head.cell(0, 1), 8.9)
    x.add_text(
        x.new_paragraph(head.cell(0, 1), rtl=False, align="right", after=2),
        "General instructions",
        color=x.BRAND_STRONG,
        size=13,
        bold=True,
    )
    x.spacer(doc, 6)
    table = x.make_table(doc, len(rules), [8.9, 8.9], borders=None)
    for index, (ar, en) in enumerate(rules):
        x.set_row(table.rows[index])
        right, left = table.cell(index, 0), table.cell(index, 1)
        x.set_cell(right, 8.9, valign="top")
        x.set_cell(left, 8.9, valign="top")
        x.add_text(x.new_paragraph(right, after=5, indent_cm=0), f"• {ar}", size=10.5)
        x.add_text(x.new_paragraph(left, rtl=False, after=5), f"• {en}", size=10.5)
    x.spacer(doc, 10)
    samples = [
        ("☒", "إجابة صحيحة التأشير", "Correctly marked"),
        ("■ ☒", "إجابة مغيَّرة: المملوء ملغى والمؤشَّر معتمد", "Changed answer: the filled box is cancelled"),
        ("☒ ☒", "علامتان: لا تُحتسب الإجابة", "Two marks: no credit"),
    ]
    marking = x.make_table(doc, len(samples), [3.0, 8.4, 6.4], borders=x.box(4, x.RULE))
    for index, (symbol, ar, en) in enumerate(samples):
        cells = [marking.cell(index, c) for c in range(3)]
        for cell, width in zip(cells, [3.0, 8.4, 6.4], strict=True):
            x.set_cell(cell, width)
        x.add_text(
            x.new_paragraph(cells[0], align="center", after=0, rtl=False), symbol, size=14, font=x.SYMBOL_FONT
        )
        x.add_text(x.new_paragraph(cells[1], after=0), ar, size=10.5)
        x.add_text(x.new_paragraph(cells[2], rtl=False, after=0), en, size=10)
    if header["instructions"]:
        par = x.new_paragraph(doc, before=10)
        x.add_text(par, "تعليمات المعلم: ", size=10.5, bold=True)
        x.add_text(par, header["instructions"], size=10.5)


# ---------- الأسئلة ----------


def section_notes(paper: dict) -> dict[int, tuple[str, str]]:
    notes: dict[int, tuple[str, str]] = {}
    questions = paper["questions"]
    for kind in ("mcq", "essay"):
        group = [q for q in questions if q["kind"] == kind]
        if not group or len(group) == len(questions):
            continue
        first, last = group[0]["number"], group[-1]["number"]
        span = f"السؤال {first}" if first == last else f"كل سؤال من {first} إلى {last}"
        span_en = f"question {first}" if first == last else f"questions {first} through {last}"
        notes[first] = (
            (
                f"اختر الإجابة الصحيحة لـ{span} بوضع علامة × في المربع المجاور للإجابة الصحيحة.",
                f"Choose the correct answer for {span_en} by putting × in the box beside it.",
            )
            if kind == "mcq"
            else (
                f"أجب عن {span} في الفراغ المخصص، مبيّنًا خطوات الحل.",
                f"For {span_en}, write your answer in the space provided and show your work.",
            )
        )
    return notes


def question_head(doc, question: dict, booklet: bool) -> None:
    marks = marks_label(question["marks"]) if question["marks"] else ""
    if booklet:
        essay = question["kind"] == "essay"
        widths = [1.3, 3.6, 2.2] if essay else [1.3, 3.6]
        table = x.make_table(doc, 1, widths, rtl=True, borders=None, align="left")
        x.set_row(table.rows[0])
        number, label = table.cell(0, 0), table.cell(0, 1)
        x.set_cell(number, widths[0], borders=x.box(12, x.BRAND, inside=False), shade=x.SHADE)
        x.add_text(
            x.new_paragraph(number, align="center", after=0, keep_next=True),
            str(question["number"]),
            color=x.BRAND_STRONG,
            size=14,
            bold=True,
        )
        x.set_cell(label, widths[1])
        x.add_text(
            x.new_paragraph(label, after=0, keep_next=True, indent_cm=0.2),
            f"{marks}{' /' if essay else ''}",
            size=10.5,
            bold=True,
        )
        if essay:
            score = table.cell(0, 2)
            x.set_cell(score, widths[2], borders=x.box(8, x.INK, inside=False))
            x.new_paragraph(score, after=0, keep_next=True, exact_pt=18)
        x.spacer(doc, 3, keep_next=True)
        return
    par = x.new_paragraph(doc, before=6, after=4, keep_next=True)
    x.add_text(
        par, f"{NBSP}السؤال {question['number']}{NBSP}", size=11.5, bold=True, color="FFFFFF", fill=x.BRAND
    )
    if marks:
        x.add_text(par, f"   {marks}", size=10, color=x.SOFT)


def option_cell(cell, index: int, part: dict, width: float, keep_next: bool) -> None:
    """keep_next يربط صف البدائل بالصف الذي يليه، فلا ينقسم سؤال الاختيار بين صفحتين."""
    x.set_cell(cell, width, valign="top")
    par = x.new_paragraph(cell, rtl=False, align="left", after=3, keep_next=keep_next)
    x.add_text(par, "☐ ", size=11, font=x.SYMBOL_FONT)
    x.add_text(par, f"{OPTION_LABELS[index]}. ", size=11, bold=True, color=x.BRAND_STRONG)
    graphs = part.get("option_graphs") or []
    if graphs and index < len(graphs):
        png, w, h = render_graph(graphs[index], compact=True)
        scale = min(1.0, 4.0 / (h / 96 * 2.54))
        x.add_picture(par, png, w / 96 * 2.54 * scale)
    else:
        rich(cell, part["options"][index], size=11, rtl=False, first=par, keep_next=keep_next)


def options_block(doc, part: dict, booklet: bool, *, keep: bool = False) -> None:
    options = part["options"]
    graphs = bool(part.get("option_graphs"))
    short = not graphs and all(len(option) <= SHORT_OPTION for option in options)
    if graphs or short:
        rows = (len(options) + 1) // 2
        width = CONTENT_CM / 2 - 0.6
        table = x.make_table(doc, rows, [width, width], rtl=False, borders=None, align="center")
        for r in range(rows):
            x.set_row(table.rows[r])
            for c in range(2):
                index = r * 2 + c
                cell = table.cell(r, c)
                last = r == rows - 1 and not keep
                if index < len(options):
                    option_cell(cell, index, part, width, not last)
                else:
                    x.set_cell(cell, width)
                    x.new_paragraph(cell, after=0, keep_next=not last)
    else:
        table = x.make_table(doc, len(options), [CONTENT_CM - 1.0], rtl=False, borders=None, align="center")
        for index in range(len(options)):
            x.set_row(table.rows[index])
            option_cell(table.cell(index, 0), index, part, CONTENT_CM - 1.0, keep or index < len(options) - 1)
    x.spacer(doc, 3, keep_next=keep)


def work_lines(part: dict) -> int:
    """أسطر الحل كما في PDF: سطر لكل درجة وسطر زائد (3 إلى 6)، وأربعة حين لا درجات، وستة على الأقل بجوار رسم.
    السطر الأخير بلا خط منقّط: يغلقه فاصل السؤال فلا يتجاور خطان."""
    lines = min(max((part["marks"] or 3) + 1, 3), 6)
    return max(lines, 6) if part.get("graph") else lines


DOTTED = {"bottom": {"val": "dotted", "sz": 6, "color": x.RULE}}


def work_box(doc, part: dict, booklet: bool, *, keep: bool = False) -> None:
    marks = part["marks"]
    if booklet:
        height_px = min(max(60 + marks * 45, 96), 300)
        height_cm = height_px / 96 * 2.54
        label = x.make_table(doc, 1, [CONTENT_CM / 2, CONTENT_CM / 2], rtl=True, borders=None)
        x.set_row(label.rows[0])
        x.set_cell(label.cell(0, 0), CONTENT_CM / 2)
        x.add_text(
            x.new_paragraph(label.cell(0, 0), after=0, keep_next=True), "وضح خطوات الحل", size=9.5, bold=True
        )
        x.set_cell(label.cell(0, 1), CONTENT_CM / 2)
        x.add_text(
            x.new_paragraph(label.cell(0, 1), rtl=False, align="left", after=0, keep_next=True),
            "Show your work",
            size=9.5,
            bold=True,
        )
        table = x.make_table(doc, 1, [CONTENT_CM - 1.4, 1.2], rtl=True, borders=None, cell_margin_cm=0.05)
        x.set_row(table.rows[0], height_cm=height_cm)
        x.set_cell(table.cell(0, 0), CONTENT_CM - 1.4, borders=x.box(12, x.INK, inside=False), valign="top")
        x.new_paragraph(table.cell(0, 0), after=0)
        x.set_cell(table.cell(0, 1), 1.2, valign="bottom")
        x.add_text(x.new_paragraph(table.cell(0, 1), align="center", after=0), str(marks), size=12, bold=True)
        x.spacer(doc, 6)
        return
    lines = work_lines(part)
    graph = part.get("graph")
    if not graph:
        table = x.make_table(doc, lines, [CONTENT_CM], borders=None)
        for r in range(lines):
            x.set_row(table.rows[r], height_cm=LINE_CM, exact=True)
            x.set_cell(table.cell(r, 0), CONTENT_CM, borders=DOTTED if r < lines - 1 else None)
            x.new_paragraph(table.cell(r, 0), after=0, line=None, exact_pt=10, keep_next=keep)
        x.spacer(doc, 4, keep_next=keep)
        return
    # الرسم يسارًا وأسطر الحل بجواره يمينًا: عمود الرسم خلية واحدة مدموجة رأسيًا، والأسطر تتوزع على ارتفاعه
    png, width, height = render_graph(graph, compact=False)
    width_cm, height_cm = width / 96 * 2.54, height / 96 * 2.54
    scale = min(1.0, SIDE_GRAPH_CM / height_cm, 7.4 / width_cm)
    side = width_cm * scale + 0.5
    widths = [CONTENT_CM - side, side]
    row_cm = max(LINE_CM, (height_cm * scale + 1.0) / lines)
    table = x.make_table(doc, lines, widths, borders=None)
    for r in range(lines):
        x.set_row(table.rows[r], height_cm=row_cm, exact=True)
        x.set_cell(table.cell(r, 0), widths[0], borders=DOTTED if r < lines - 1 else None)
        x.new_paragraph(table.cell(r, 0), after=0, line=None, exact_pt=10, keep_next=True)
    merged = table.cell(0, 1).merge(table.cell(lines - 1, 1))
    for extra in merged.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)
    picture = x.new_paragraph(merged, rtl=False, align="center", after=0, line=None, keep_next=True)
    x.add_picture(picture, png, width_cm * scale)
    caption = x.new_paragraph(merged, rtl=False, align="center", after=0, keep_next=True)
    x.add_math(caption, f"y={graph['label']}(x)")
    x.spacer(doc, 4, keep_next=keep)


def question_block(
    doc, question: dict, booklet: bool, notes: dict, last_mcq: int, count: int, *, keep: bool = False
) -> None:
    """keep: السؤال الأخير في ورقة غير الكراسة يُربط بسطر «انتهت الأسئلة» فلا ينفرد السطر بصفحة."""
    note = notes.get(question["number"])
    if note:
        par = x.new_paragraph(doc, before=4, after=1, keep_next=True, shade=x.SHADE)
        x.add_text(par, note[0], size=10, bold=True)
        if booklet:
            en = x.new_paragraph(doc, rtl=False, align="left", after=4, keep_next=True, shade=x.SHADE)
            x.add_text(en, note[1], size=9.5)
    question_head(doc, question, booklet)
    parts = question["parts"]
    for position, part in enumerate(parts):
        bind = keep and position == len(parts) - 1
        side = not booklet and bool(part.get("graph")) and not part["options"]
        stem = x.new_paragraph(doc, before=2, after=3, keep_next=True)
        label = part.get("label") or ""
        if label:
            # ترقيم عربي: «.A» بصريًا (الحرف يمينًا ثم النقطة) ثم مسافة قبل نص السؤال
            x.add_text(stem, f"{label}.{x.RLM} ", size=11, bold=True, force_rtl=True, color=x.BRAND_STRONG)
        rich(doc, part["stem"], size=11, first=stem)
        if label and not booklet and part.get("marks"):
            x.add_text(stem, f"  ({part['marks']})", size=9.5, color=x.SOFT)
        if part.get("graph") and not side:
            graph_picture(doc, part["graph"], compact=booklet)
            if not booklet:
                caption = x.new_paragraph(
                    doc, rtl=False, align="center", after=3, keep_next=bool(part["options"])
                )
                x.add_math(caption, f"y={part['graph']['label']}(x)")
        if part["options"]:
            options_block(doc, part, booklet, keep=bind)
        else:
            work_box(doc, part, booklet, keep=bind)
    if booklet and question["number"] == last_mcq and last_mcq < count:
        _bilingual_rule(doc, "انتهت الأسئلة الموضوعية", "End of multiple-choice questions")


def _bilingual_rule(doc, ar: str, en: str) -> None:
    table = x.make_table(
        doc, 1, [CONTENT_CM / 2, CONTENT_CM / 2], borders={"top": x.BRAND_EDGE, "bottom": x.BRAND_EDGE}
    )
    x.set_row(table.rows[0])
    x.set_cell(table.cell(0, 0), CONTENT_CM / 2, shade=x.SHADE)
    x.add_text(x.new_paragraph(table.cell(0, 0), after=0), ar, size=10, bold=True)
    x.set_cell(table.cell(0, 1), CONTENT_CM / 2, shade=x.SHADE)
    x.add_text(x.new_paragraph(table.cell(0, 1), rtl=False, align="left", after=0), en, size=10, bold=True)
    x.spacer(doc, 6)


def sheet(doc, paper: dict, header: dict, *, page_break: bool = False) -> None:
    booklet = paper["kind"] == "exam"
    if booklet:
        cover_page(doc, header, paper)
        x.spacer(doc, 2, page_break=True)
    else:
        paper_header(doc, header, page_break=page_break)
    notes = section_notes(paper)
    questions = paper["questions"]
    last_mcq = max((q["number"] for q in questions if q["kind"] == "mcq"), default=0)
    first_essay = next((q["number"] for q in questions if q["kind"] != "mcq"), 0)
    for index, question in enumerate(questions):
        if booklet and question["number"] == first_essay and last_mcq:
            x.spacer(doc, 1, page_break=True)  # القسم المقالي يبدأ صفحة جديدة كما في PDF
        final = index == len(questions) - 1
        question_block(doc, question, booklet, notes, last_mcq, len(questions), keep=final and not booklet)
        closes_section = booklet and question["number"] == last_mcq and last_mcq < len(questions)
        if index < len(questions) - 1 and not closes_section:
            # خط مستقيم بعرض النص كاملًا (بين الهامشين) يفصل السؤال عن الذي يليه
            x.new_paragraph(doc, before=2, after=6, line=None, exact_pt=3, bottom=("single", 6, x.RULE))
    if booklet:
        _bilingual_rule(doc, "انتهت جميع الأسئلة", "End of all questions")
    foot = x.make_table(
        doc, 1, [CONTENT_CM / 2, CONTENT_CM / 2], borders={"top": {"val": "single", "sz": 4, "color": x.RULE}}
    )
    x.set_cell(foot.cell(0, 0), CONTENT_CM / 2)
    x.add_text(
        x.new_paragraph(foot.cell(0, 0), after=0), "" if booklet else "انتهت الأسئلة", size=9, color=x.SOFT
    )
    x.set_cell(foot.cell(0, 1), CONTENT_CM / 2)
    x.add_text(
        x.new_paragraph(foot.cell(0, 1), align="left", after=0),
        f"رقم النموذج {paper['seed']}",
        size=9,
        color=x.SOFT,
    )
    if booklet:
        score_page(doc, paper)


def score_page(doc, paper: dict) -> None:
    mcq = [q for q in paper["questions"] if q["kind"] == "mcq"]
    essays = [q for q in paper["questions"] if q["kind"] != "mcq"]
    rows: list[tuple[str, int]] = []
    if mcq:
        first, last = mcq[0]["number"], mcq[-1]["number"]
        rows.append((f"{first}" if first == last else f"{first} – {last}", sum(q["marks"] for q in mcq)))
    rows += [(str(q["number"]), q["marks"]) for q in essays]
    total = sum(marks for _, marks in rows)
    x.add_text(
        x.new_paragraph(doc, align="center", page_break=True, after=4),
        "الطلاب: لا تكتب على هذه الصفحة",
        color=x.BRAND_STRONG,
        size=11,
        bold=True,
    )
    x.add_text(
        x.new_paragraph(doc, align="center", before=6, after=8),
        "جدول رصد الدرجات",
        size=16,
        bold=True,
        color=x.BRAND_STRONG,
    )
    widths = [3.2, 3.0, 4.0, 3.8, 3.8]
    table = x.make_table(doc, len(rows) + 2, widths, borders=x.box(8, x.RULE))
    heads = ["رقم السؤال", "الدرجة", "درجة الطالب", "المصحح", "المراجع"]
    for c, text in enumerate(heads):
        cell = table.cell(0, c)
        x.set_cell(cell, widths[c], shade=x.BRAND)
        x.add_text(x.new_paragraph(cell, align="center", after=0), text, size=10.5, bold=True, color=x.WHITE)
    x.set_row(table.rows[0], header=True)
    for r, (label, marks) in enumerate(rows, start=1):
        x.set_row(table.rows[r], height_cm=1.0)
        values = [label, str(marks), "", "", ""]
        for c, text in enumerate(values):
            cell = table.cell(r, c)
            x.set_cell(cell, widths[c])
            x.add_text(x.new_paragraph(cell, align="center", after=0, rtl=False), text, size=11, bold=c == 0)
    last = len(rows) + 1
    x.set_row(table.rows[last], height_cm=1.0)
    for c, text in enumerate(["المجموع", str(total), "", "", ""]):
        cell = table.cell(last, c)
        x.set_cell(cell, widths[c], shade=x.SHADE)
        x.add_text(x.new_paragraph(cell, align="center", after=0), text, size=11, bold=True)
    x.add_text(x.new_paragraph(doc, before=14), f"الدرجة كتابةً: {'.' * 60}", size=12)


# ---------- ورقة التظليل والمفتاح ----------


def answer_sheet(doc, paper: dict, header: dict, *, answers: bool) -> None:
    rows = [
        (q["number"], q["parts"][0].get("answer_index", -1)) for q in paper["questions"] if q["kind"] == "mcq"
    ]
    if not rows:
        return
    title = f"{'مفتاح ورقة الإجابة' if answers else 'ورقة الإجابة'}: {header['title']}"
    paper_header(doc, {**header, "title": title, "instructions": ""}, compact=True, page_break=True)
    if not answers:
        student = x.make_table(doc, 1, [9.0, 4.4, 4.4], borders=None)
        for cell, text, w in zip(
            student.rows[0].cells,
            [f"اسم الطالب: {DOTS}{DOTS}", f"الشعبة: {header['section'] or DOTS}", f"الرقم: {DOTS}"],
            [9.0, 4.4, 4.4],
            strict=True,
        ):
            x.set_cell(cell, w)
            labelled(x.new_paragraph(cell, before=4, after=2), text, size=10.5)
    note = (
        "الدوائر المظلَّلة هي الإجابات الصحيحة لهذا النموذج."
        if answers
        else "ظلّل دائرة واحدة فقط لكل سؤال بقلم أزرق أو أسود. التظليل في أكثر من دائرة يُلغي الإجابة."
    )
    x.add_text(x.new_paragraph(doc, before=6, after=6), note, size=10.5, color=x.SOFT)
    columns = 2 if len(rows) > 12 else 1
    per = -(-len(rows) // columns)
    block = 5  # رقم + أربعة خيارات
    widths: list[float] = []
    for c in range(columns):
        widths += [1.2] + [1.35] * 4
        if c < columns - 1:
            widths.append(1.6)
    table = x.make_table(doc, per, widths, rtl=False, borders=None)
    for r in range(per):
        x.set_row(table.rows[r], height_cm=0.9)
        for c in range(columns):
            base = c * (block + 1)
            row = c * per + r
            for k in range(block):
                cell = table.cell(r, base + k)
                x.set_cell(cell, widths[base + k])
                if row >= len(rows):
                    x.new_paragraph(cell, after=0)
                    continue
                number, correct = rows[row]
                if k == 0:
                    x.add_text(
                        x.new_paragraph(cell, align="center", after=0, rtl=False),
                        str(number),
                        color=x.BRAND_STRONG,
                        size=11,
                        bold=True,
                    )
                    continue
                filled = answers and k - 1 == correct
                par = x.new_paragraph(cell, align="center", after=0, rtl=False)
                x.add_text(par, "●" if filled else "○", size=17, font=x.SYMBOL_FONT)
                x.add_text(par, f" {OPTION_LABELS[k - 1]}", size=9, bold=True)
    x.add_text(
        x.new_paragraph(doc, before=10),
        f"{len(rows)} سؤالًا موضوعيًا    ·    رقم النموذج {paper['seed']}",
        size=9,
        color=x.SOFT,
    )


def _mark_text(marks: float) -> str:
    """الدرجة كما تُكتب في الجدول: 1 و0.5 و1.5، وفارغة للصفر."""
    return f"{marks:g}" if marks else ""


def _key_rows(part: dict) -> list[dict]:
    """صفوف الجزء في المفتاح: صف لكل بند من توزيع الدرجة (خطوات ثم الجواب النهائي)، أو صف واحد بلا توزيع.

    يطابق keyRows في PaperSheet.vue؛ ترقيم الخطوات متصل عبر الصفوف.
    """
    items = part.get("marking") or []
    if not items:
        return [
            {
                "steps": part.get("steps") or [],
                "start": 1,
                "marks": part.get("marks") or 0,
                "final": False,
                "plain": True,
            }
        ]
    rows, start = [], 1
    for item in items:
        rows.append(
            {
                "steps": item["steps"],
                "start": start,
                "marks": item["marks"],
                "final": item.get("final", False),
                "plain": False,
            }
        )
        start += len(item["steps"])
    return rows


def key_pages(doc, paper: dict, header: dict, *, page_break: bool = True) -> None:
    booklet = paper["kind"] == "exam"
    title = f"{'دليل تقدير الدرجات' if booklet else 'مفتاح الحل'}: {header['title']}"
    paper_header(doc, {**header, "title": title}, compact=True, page_break=page_break)
    mcq = [
        (q["number"], q["parts"][0].get("answer_index", -1))
        for q in paper["questions"]
        if q["kind"] == "mcq" and q["parts"][0].get("answer_index", -1) >= 0
    ]
    # أوراق العمل بلا درجات: لا عمود درجة فارغ، وعرضه يذهب لعمود الإجابة
    has_marks = any(part.get("marks") for question in paper["questions"] for part in question["parts"])
    if mcq:
        x.add_text(
            x.new_paragraph(doc, before=4, after=3, keep_next=True),
            "إجابات الأسئلة الموضوعية",
            color=x.BRAND_STRONG,
            size=12,
            bold=True,
        )
        per_row = min(10, len(mcq))
        chunks = [mcq[i : i + per_row] for i in range(0, len(mcq), per_row)]
        widths = [2.6] + [1.52] * per_row
        table = x.make_table(doc, len(chunks) * 2, widths, borders=x.box(6, x.RULE), align="left")
        for index, chunk in enumerate(chunks):
            for offset, (label, shade) in enumerate((("رقم السؤال", x.SHADE), ("رمز الإجابة", None))):
                r = index * 2 + offset
                x.set_row(table.rows[r])
                cell = table.cell(r, 0)
                x.set_cell(cell, widths[0], shade=x.BRAND)
                x.add_text(
                    x.new_paragraph(cell, align="center", after=0), label, size=9, bold=True, color=x.WHITE
                )
                for c in range(per_row):
                    target = table.cell(r, c + 1)
                    x.set_cell(target, widths[c + 1], shade=shade)
                    if c < len(chunk):
                        number, answer = chunk[c]
                        text = str(number) if offset == 0 else OPTION_LABELS[answer]
                        x.add_text(
                            x.new_paragraph(target, align="center", after=0, rtl=False),
                            text,
                            size=10.5,
                            bold=True,
                        )
                    else:
                        x.new_paragraph(target, after=0)
        x.spacer(doc, 8)
        x.add_text(
            x.new_paragraph(doc, before=4, after=3, keep_next=True),
            "الحلول والخطوات بدرجاتها" if has_marks else "الحلول والخطوات",
            color=x.BRAND_STRONG,
            size=12,
            bold=True,
        )
    # مع الدرجات: عمود لدرجة كل بند بعد الخطوات، وعمود لمجموع الجزء في آخر الجدول
    widths = [1.7, 7.9, 1.5, 3.1, 1.9, 1.7] if has_marks else [1.9, 10.9, 3.1, 1.9]
    heads = (
        ["السؤال", "الإجابة والخطوات", "الدرجة", "الدرس", "المستوى", "المجموع"]
        if has_marks
        else ["السؤال", "الإجابة والخطوات", "الدرس", "المستوى"]
    )
    lesson_col, level_col = (3, 4) if has_marks else (2, 3)
    per_item = {1, 2} if has_marks else {1}  # أعمدة تتكرر لكل بند؛ ما عداها خلايا الجزء
    centered = {0, 2, 5} if has_marks else {0}
    table = x.make_table(doc, 1, widths, borders=x.box(6, x.RULE))
    for c, text in enumerate(heads):
        cell = table.cell(0, c)
        x.set_cell(cell, widths[c], shade=x.BRAND)
        x.add_text(x.new_paragraph(cell, align="center", after=0), text, size=10, bold=True, color=x.WHITE)
    x.set_row(table.rows[0], header=True)
    for question in paper["questions"]:
        for part in question["parts"]:
            rows = _key_rows(part)
            label = f"{question['number']}{(' ' + part['label']) if part.get('label') else ''}"
            built = []
            for index, entry in enumerate(rows):
                row = table.add_row()
                built.append(row)
                x.set_row(row)
                cells = row.cells
                # خلايا الجزء (السؤال والدرس والمستوى والمجموع) تمتد رأسيًا على صفوف بنوده
                merge = ("restart" if index == 0 else "continue") if len(rows) > 1 else ""
                for c, width in enumerate(widths):
                    x.set_cell(
                        cells[c],
                        width,
                        valign="center" if c in centered else "top",
                        vmerge="" if c in per_item else merge,
                    )
                if entry["plain"] or entry["final"]:
                    first = None
                    if entry["final"]:
                        first = x.new_paragraph(cells[1], after=1)
                        x.add_text(first, "الجواب النهائي: ", size=10.5, bold=True, color=x.BRAND_STRONG)
                    rich(cells[1], part["answer"], size=10.5, bold=True, after=2, first=first)
                for number, step in enumerate(entry["steps"], start=entry["start"]):
                    par = x.new_paragraph(cells[1], after=1, indent_cm=0.0)
                    x.add_text(par, f"{number}.{x.LRM} ", size=9.5, color=x.SOFT)
                    rich(cells[1], step, size=9.5, first=par)
                if has_marks:
                    x.add_text(
                        x.new_paragraph(cells[2], align="center", after=0, rtl=False),
                        _mark_text(entry["marks"]),
                        size=10.5,
                    )
                if index:
                    continue
                x.add_text(
                    x.new_paragraph(cells[0], align="center", after=0),
                    label,
                    size=10.5,
                    bold=True,
                    color=x.BRAND_STRONG,
                )
                x.add_text(x.new_paragraph(cells[lesson_col], after=0), part.get("lesson", ""), size=9)
                x.add_text(
                    x.new_paragraph(cells[level_col], align="center", after=0),
                    LEVEL_NAMES.get(part.get("level", ""), ""),
                    size=9,
                )
                if has_marks:
                    x.add_text(
                        x.new_paragraph(cells[5], align="center", after=0, rtl=False),
                        str(part["marks"] or ""),
                        size=10.5,
                        bold=True,
                    )
            # بنود الجزء لا تنقسم بين صفحتين: كل صف يلحق بما بعده حتى الجواب النهائي
            for row in built[:-1]:
                x.keep_row_with_next(row)
    x.add_text(x.new_paragraph(doc, before=8), f"رقم النموذج {paper['seed']}", size=9, color=x.SOFT)


# ---------- الوثيقة ----------


def _setup(doc: Document) -> None:
    normal = doc.styles["Normal"].element
    for old in normal.findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr"):
        normal.remove(old)
    normal.append(
        parse_xml(
            f'<w:rPr {W}><w:rFonts w:ascii="{x.FONT}" w:hAnsi="{x.FONT}" w:cs="{x.FONT}" w:eastAsia="{x.FONT}"/>'
            '<w:sz w:val="22"/><w:szCs w:val="22"/><w:lang w:val="en-US" w:eastAsia="ar-QA" w:bidi="ar-QA"/></w:rPr>'
        )
    )
    doc.core_properties.author = "أوراق"
    doc.core_properties.language = "ar-QA"


def _configure_section(section, footer_text: str) -> None:
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.left_margin = section.right_margin = Cm(1.6)
    section.top_margin, section.bottom_margin = Cm(1.5), Cm(1.8)
    section.footer_distance = Cm(0.8)
    sect_pr = section._sectPr
    if sect_pr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}bidi") is None:
        sect_pr.insert_element_before(
            parse_xml(f"<w:bidi {W}/>"), "w:rtlGutter", "w:docGrid", "w:printerSettings", "w:sectPrChange"
        )
    section.footer.is_linked_to_previous = False
    footer = section.footer
    for paragraph in list(footer.paragraphs)[1:]:
        paragraph._p.getparent().remove(paragraph._p)
    # تذييل الهوية: خط علوي، اسم المنصة يمينًا، عنوان الورقة وسطًا، رقم الصفحة من المجموع يسارًا
    widths = [4.5, 9.8, 3.5]
    table = x.make_table(footer, 1, widths, borders={"top": x.BRAND_EDGE}, cell_margin_cm=0.05)
    x.set_row(table.rows[0])
    for cell, width in zip(table.rows[0].cells, widths, strict=True):
        x.set_cell(cell, width, valign="top")
    x.add_picture(
        x.new_paragraph(table.cell(0, 0), rtl=False, align="right", before=3, after=0, line=None),
        LOGO,
        FOOTER_LOGO_CM,
    )
    middle = x.new_paragraph(table.cell(0, 1), align="center", before=3, after=0, line=None)
    x.add_text(middle, footer_text, size=8, color=x.SOFT)
    pages = x.new_paragraph(table.cell(0, 2), align="left", before=3, after=0, line=None)
    x.add_text(pages, "صفحة ", size=8.5)
    x.add_field(pages, " PAGE ", size=8.5)
    x.add_text(pages, " من ", size=8.5)
    x.add_field(pages, " NUMPAGES ", size=8.5)
    # الفقرة الفارغة الأصلية تسبق الجدول؛ تُحذف وتُضاف فقرة ختامية دقيقة (الحاوية تنتهي بفقرة لا بجدول)
    for paragraph in footer.paragraphs:
        paragraph._p.getparent().remove(paragraph._p)
    x.spacer(footer, 1)


def bundle_cover(doc, header: dict, bundle: dict) -> None:
    """غلاف الحزمة: ترويسة بالشعار ثم ملخص وفهرس الدروس ورقم الحزمة."""
    plan = bundle["plan"]
    cover = {
        **header,
        "title": BUNDLE_COVER_TITLE,
        "minutes": None,
        "total": 0,
        "instructions": "",
        "form": "",
    }
    paper_header(doc, cover, compact=True)
    total = sum(entry["count"] for entry in plan)
    x.add_text(
        x.new_paragraph(doc, before=6, after=8),
        f"{len(plan)} ورقة عمل، {total} مسألة، مرتبة من السهل إلى مهارات التفكير العليا.",
        size=11,
        color=x.SOFT,
    )
    x.add_text(
        x.new_paragraph(doc, after=4, keep_next=True), "الفهرس", size=13, bold=True, color=x.BRAND_STRONG
    )
    widths = [2.0, 8.6, 2.0, 5.2]
    table = x.make_table(doc, len(plan) + 1, widths, borders=x.box(6, x.RULE))
    for c, text in enumerate(["الدرس", "العنوان", "المسائل", "المستويات"]):
        x.set_cell(table.cell(0, c), widths[c], shade=x.BRAND)
        x.add_text(
            x.new_paragraph(table.cell(0, c), align="center", after=0),
            text,
            size=10,
            bold=True,
            color=x.WHITE,
        )
    x.set_row(table.rows[0], header=True)
    for r, entry in enumerate(plan, start=1):
        x.set_row(table.rows[r], height_cm=0.72)
        levels = "، ".join(
            f"{name} {entry['levels'][code]}"
            for code, name in LEVEL_NAMES.items()
            if entry["levels"].get(code)
        )
        cells = [table.cell(r, c) for c in range(4)]
        code = x.new_paragraph(cells[0], align="center", after=0, rtl=False)
        x.add_text(code, entry["lesson"], size=10.5, bold=True, color=x.BRAND_STRONG)
        x.add_text(x.new_paragraph(cells[1], after=0), entry["title"], size=10.5)
        count = x.new_paragraph(cells[2], align="center", after=0, rtl=False)
        x.add_text(count, str(entry["count"]), size=10.5)
        x.add_text(x.new_paragraph(cells[3], after=0), levels, size=9.5, color=x.SOFT)
    x.add_text(x.new_paragraph(doc, before=10), f"رقم الحزمة {bundle['seed']}", size=9, color=x.SOFT)


def build_docx(payload: dict[str, Any]) -> bytes:
    """الحمولة هي PdfIn.dict(): papers وprofile وdate وsection وshow_key وbubble، وbundle لحزمة أوراق العمل."""
    papers = payload["papers"]
    profile = payload["profile"]
    bundle = payload.get("bundle")
    multi = len(papers) > 1 and not bundle
    doc = Document()
    _setup(doc)
    x.embed_fonts(doc)
    headers = [
        header_of(p, profile, payload.get("date", ""), payload.get("section", ""), multi) for p in papers
    ]
    if bundle:
        # الحزمة قسم واحد بتذييل واحد: غلاف بفهرس، ثم كل ورقة تبدأ صفحة جديدة
        _configure_section(doc.sections[0], BUNDLE_COVER_TITLE)
        bundle_cover(doc, headers[0], bundle)
        for paper, header in zip(papers, headers, strict=True):
            sheet(doc, paper, header, page_break=True)
    else:
        for index, (paper, header) in enumerate(zip(papers, headers, strict=True)):
            section = doc.sections[0] if index == 0 else doc.add_section(WD_SECTION.NEW_PAGE)
            footer = (
                " – ".join(v for v in (header["subject"], header["title"], short_grade(header["grade"])) if v)
                if paper["kind"] == "exam"
                else header["title"]
            )
            _configure_section(section, footer)
            sheet(doc, paper, header)
            if payload.get("bubble") and any(q["kind"] == "mcq" for q in paper["questions"]):
                answer_sheet(doc, paper, header, answers=False)
    if payload.get("show_key"):
        section = doc.add_section(WD_SECTION.NEW_PAGE)
        _configure_section(section, "مفتاح الحل")
        for index, (paper, header) in enumerate(zip(papers, headers, strict=True)):
            # القسم الجديد يبدأ صفحة بنفسه؛ فاصل الصفحة قبل الترويسة لما بعد المفتاح الأول فقط
            key_pages(doc, paper, header, page_break=bool(index))
            if payload.get("bubble") and not bundle and any(q["kind"] == "mcq" for q in paper["questions"]):
                answer_sheet(doc, paper, header, answers=True)
    # أول فقرة في الوثيقة فارغة من python-docx قبل إضافة أي شيء؛ تُحذف إن كانت فارغة تمامًا.
    body = doc.element.body
    first = body[0]
    if first.tag.endswith("}p") and len(first) == 0:
        body.remove(first)
    stream = BytesIO()
    doc.save(stream)
    _ = (Pt, to_omml)
    return stream.getvalue()
