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

from apps.papers.word.builder import isolate_number_ranges
from apps.papers.word.school.fill import fill

from .domain.prep_sheet import PrepSheet

TEMPLATE = (Path(__file__).parent / "word" / "assets" / "ministry" / "prep.docx").read_bytes()
TEACH_ROW, CHECK_ROW = 13, 14
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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
        "{terms_ar}": "",
        "{terms_en}": "",
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
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def prep_filename(sheet: PrepSheet) -> str:
    return f"prep-{sheet.course}-{sheet.lesson}-k{sheet.k}.docx"
