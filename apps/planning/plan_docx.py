"""تصدير الخطة الفصلية DOCX عربيًا من اليمين لليسار: جدول أسابيع الوزارة وبنودها وحصصها وتواريخ حصص الشعبة الفعلية.

الأعمدة: الأسبوع، الزمن، البند، عدد الحصص، تواريخ الحصص في الشعبة. أعمدة النصوص التربوية في نموذج الوزارة (الكفايات والقيم ومكتسبات
التعلم) غير مولَّدة: نصوصها محتوى محميّ خارج المستودع، فيملؤها المعلم من وثيقته. المخرج حتمي لمدخلاته.
"""

from __future__ import annotations

from io import BytesIO

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .domain.calendar_engine import Plan
from .domain.semester_plan import PlanEntry, TermPlan

FONT = "Noto Naskh Arabic"
BRAND = "8E2433"  # BRAND في apps/papers/word/ooxml.py
SOFT = "F6EEEF"
COPYRIGHT = "© سفيان مسيف  55296286"  # نظير COPYRIGHT_* في apps/papers/word/builder.py
HEADER = ("الأسبوع", "الزمن", "البند", "عدد الحصص", "تواريخ الحصص")
WIDTHS = (2.2, 4.6, 8.8, 2.6, 8.0)  # سم، مجموعها عرض محتوى A4 أفقيًا بهوامش 1.5 سم

LABELS = {
    "orientation": "تهيئة بداية الفصل الدراسي",
    "exam:midterm": "اختبار منتصف الفصل",
    "review:midterm": "مراجعة اختبار منتصف الفصل",
    "review:final": "مراجعة اختبار نهاية الفصل",
    "project": "مشروع STEM",
    "support": "دعم وتثبيت المهارات الرياضية",
}


def entry_label(e: PlanEntry) -> str:
    if e.kind == "lesson":
        return f"الدرس {e.lesson}"
    if e.kind == "quiz":
        return f"مراجعة واختبار الوحدة {e.unit}"
    return LABELS[e.key]


def _short(d) -> str:
    return f"{d.day}/{d.month}"


def _rtl_run(par, text: str, bold: bool = False, color: str | None = None, size: float = 11) -> None:
    run = par.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    props = run._r.get_or_add_rPr()
    fonts = OxmlElement("w:rFonts")
    for attr in ("w:ascii", "w:hAnsi", "w:cs"):
        fonts.set(qn(attr), FONT)
    props.insert(0, fonts)
    props.append(OxmlElement("w:rtl"))


def _rtl_par(par) -> None:
    par._p.get_or_add_pPr().append(OxmlElement("w:bidi"))
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "left")  # في فقرة bidi تعني «left» الحافة اليمنى (بداية السطر)
    par._p.get_or_add_pPr().append(jc)


def _shade(cell, fill: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shd)


def _cell(cell, text: str, *, bold: bool = False, color: str | None = None, fill: str | None = None) -> None:
    par = cell.paragraphs[0]
    _rtl_par(par)
    _rtl_run(par, text, bold=bold, color=color)
    if fill:
        _shade(cell, fill)


def plan_docx(
    plan: TermPlan,
    placed: Plan,
    title: str = "الخطة الفصلية للرياضيات · المستوى العاشر · الفصل الدراسي الأول",
) -> bytes:
    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Cm(29.7), Cm(21.0)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Cm(1.5))
    bidi = OxmlElement("w:bidi")
    grid = section._sectPr.find(qn("w:docGrid"))
    if grid is not None:
        grid.addprevious(bidi)  # ترتيب عناصر sectPr: bidi قبل docGrid
    else:
        section._sectPr.append(bidi)

    heading = doc.add_paragraph()
    _rtl_par(heading)
    _rtl_run(heading, title, bold=True, color=BRAND, size=16)

    table = doc.add_table(rows=1, cols=len(HEADER))
    table.style = "Table Grid"
    style = table._tbl.tblPr.find(qn("w:tblStyle"))
    visual = OxmlElement("w:bidiVisual")
    if style is not None:
        style.addnext(visual)  # بعد tblStyle وقبل tblW كما في المخطط
    else:
        table._tbl.tblPr.insert(0, visual)
    for cell, text, width in zip(table.rows[0].cells, HEADER, WIDTHS, strict=True):
        _cell(cell, text, bold=True, color="FFFFFF", fill=BRAND)
        cell.width = Cm(width)

    spans: dict[str, list] = {}
    for p in placed.placements:
        spans.setdefault(p.item_id, []).append(p.session.day)

    seen: dict[str, int] = {}
    for week in plan.weeks:
        for k, e in enumerate(week.entries):
            row = table.add_row().cells
            fill = SOFT if week.n % 2 == 0 else None
            first = k == 0
            seen[e.key] = seen.get(e.key, 0) + e.periods
            days = sorted(spans.get(e.key, ()))
            part = days[seen[e.key] - e.periods : seen[e.key]]  # حصص هذا الأسبوع من البند الممتد
            values = (
                str(week.n) if first else "",
                f"{_short(week.start)} – {_short(week.end)}" if first else "",
                entry_label(e),
                str(e.periods),
                "، ".join(_short(d) for d in part),
            )
            for cell, text, width in zip(row, values, WIDTHS, strict=True):
                _cell(cell, text, fill=fill)
                cell.width = Cm(width)

    footer = section.footer.paragraphs[0]
    _rtl_par(footer)
    _rtl_run(footer, COPYRIGHT, size=8)

    out = BytesIO()
    doc.save(out)
    return out.getvalue()
