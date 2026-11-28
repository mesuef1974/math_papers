"""تحضير الحصة في Word بنموذج الوزارة (القرار 6 في docs/lesson_prep_plan.md).

القالب `word/assets/ministry/prep.docx` يبقى كما هو (الترويسة والكفايات والقيم والوسائل والمعايير المهنية والتأمل وتوقيع
المنسق للمعلم)، وتُملأ رموزه من `PrepSheet`. كتلة الهدف صفّان (التعليم والتحقق، وخانتا الهدف والزمن مدموجتان رأسيًا)
تُنسخ مرة لكل هدف قبل الملء. الملء يجمع نص الفقرة الموزَّع على أشواط ثم يستبدل (`papers.word.school.fill`).
"""

from __future__ import annotations

import copy
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from apps.papers.word.builder import isolate_number_ranges
from apps.papers.word.school.fill import fill

from .domain.prep_sheet import PrepSheet

TEMPLATE = (Path(__file__).parent / "word" / "assets" / "ministry" / "prep.docx").read_bytes()
TEACH_ROW, CHECK_ROW = 13, 14
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


GAP_TWIPS, TAIL_TWIPS = 120, 20  # الفاصل بين جداول القالب 6pt، والفقرة الختامية 1pt


def _shrink(paragraph, twips: int) -> None:
    """فقرة فارغة بارتفاع ثابت صغير: `spacing` بعد `bidi` وقبل `rPr` كما يرتّب المخطط."""
    pr = paragraph.find(qn("w:pPr"))
    if pr is None:
        pr = OxmlElement("w:pPr")
        paragraph.insert(0, pr)
    for old in pr.findall(qn("w:spacing")):
        pr.remove(old)
    spacing = OxmlElement("w:spacing")
    for key, value in (("before", "0"), ("after", "0"), ("line", str(twips)), ("lineRule", "exact")):
        spacing.set(qn(f"w:{key}"), value)
    mark = pr.find(qn("w:rPr"))
    if mark is None:
        pr.append(spacing)
    else:
        mark.addprevious(spacing)
        for old in mark.findall(qn("w:sz")):
            mark.remove(old)
        size = OxmlElement("w:sz")
        size.set(qn("w:val"), "2")
        mark.append(size)


def _is_blank(element) -> bool:
    return (
        element.tag == qn("w:p")
        and not "".join(element.itertext()).strip()
        and element.find(".//" + qn("w:drawing")) is None
    )


def _tighten(document) -> None:
    """يحوّل فواصل القالب الفارغة إلى فاصل واحد صغير بين كل جدولين وفقرة ختامية بحجم 1pt.

    كل فقرة فارغة بالارتفاع العادي كانت تُحسب سطرًا كاملًا؛ إن امتلأت الصفحة بالأهداف المحقونة سقطت الفقرات
    الزائدة وحدها في صفحة شبه فارغة. يبقى فاصل واحد على الأقل لأن Word يدمج جدولين متجاورين بلا فقرة بينهما.
    """
    body = document.element.body
    run: list = []
    for child in [*body, None]:
        if child is not None and _is_blank(child):
            run.append(child)
            continue
        if run:
            last = child is None or child.tag == qn("w:sectPr")
            for extra in run[1:]:
                body.remove(extra)
            _shrink(run[0], TAIL_TWIPS if last else GAP_TWIPS)
            run = []


def _keep_objective_rows_together(rows) -> None:
    """صفّا الهدف (التعليم ثم التحقق) في صفحة واحدة، ولا ينقسم أي صف بين صفحتين متى اتسع له."""
    for tr in rows:
        pr = tr.find(qn("w:trPr"))
        if pr is None:
            pr = OxmlElement("w:trPr")
            tr.insert(0, pr)
        if pr.find(qn("w:cantSplit")) is None:
            pr.insert(0, OxmlElement("w:cantSplit"))
    for paragraph in rows[0].iter(qn("w:p")):
        pr = paragraph.find(qn("w:pPr"))
        if pr is None:
            pr = OxmlElement("w:pPr")
            paragraph.insert(0, pr)
        if pr.find(qn("w:keepNext")) is None:
            style = pr.find(qn("w:pStyle"))  # keepNext بعد pStyle مباشرة كما يرتّب المخطط
            keep = OxmlElement("w:keepNext")
            pr.insert(0 if style is None else list(pr).index(style) + 1, keep)


def _minutes(value: int) -> str:
    return f"{value} د"


def prep_docx(sheet: PrepSheet, teacher: str) -> bytes:
    document = Document(BytesIO(TEMPLATE))
    table = document.tables[0]
    teach, check = table.rows[TEACH_ROW]._tr, table.rows[CHECK_ROW]._tr
    blank = (copy.deepcopy(teach), copy.deepcopy(check))
    pairs = [(teach, check)]
    anchor = check
    for _ in sheet.objectives[1:]:
        pair = (copy.deepcopy(blank[0]), copy.deepcopy(blank[1]))
        anchor.addnext(pair[0])
        pair[0].addnext(pair[1])
        anchor = pair[1]
        pairs.append(pair)
    for (teach_tr, check_tr), row in zip(pairs, sheet.objectives, strict=True):
        _keep_objective_rows_together([teach_tr, check_tr])
        fill(
            [teach_tr, check_tr],
            {
                "{objective}": row.text,
                "{teach_activity}": row.teach_activity,
                "{teach_assessment}": row.teach_assessment,
                "{check_activity}": row.check_activity,
                "{check_assessment}": row.check_assessment,
                "{objective_time}": _minutes(row.teach_minutes + row.check_minutes),
            },
        )
    mapping = {
        "{year}": isolate_number_ranges(sheet.year),
        "{semester}": sheet.semester,
        "{teacher}": teacher,
        "{unit}": sheet.unit_label,
        "{lesson_title}": f"{sheet.lesson} {sheet.lesson_title}".strip(),
        "{grade}": sheet.grade,
        "{day_date}": sheet.day_date,
        "{outcomes}": sheet.outcomes,
        "{terms_ar}": "، ".join(ar for ar, _ in sheet.terms),
        "{terms_en}": ", ".join(en for _, en in sheet.terms if en),
        "{main_sources}": sheet.main_sources,
        "{support_sources}": sheet.support_sources,
        "{warmup}": sheet.warmup,
        "{warmup_time}": _minutes(sheet.warmup_minutes),
        "{closing}": sheet.closing,
        "{closing_time}": _minutes(sheet.closing_minutes),
        "{homework}": sheet.homework,
    }
    parts = [document.element.body]
    for section in document.sections:
        parts += [section.header._element, section.footer._element]
    fill(parts, mapping)
    _tighten(document)
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def prep_filename(sheet: PrepSheet) -> str:
    return f"prep-{sheet.course}-{sheet.lesson}-k{sheet.k}.docx"
