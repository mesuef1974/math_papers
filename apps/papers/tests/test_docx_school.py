"""Word بقالب المدرسة: الغلاف من ملف القالب بحقوله مملوءة، وإطار لكل سؤال، وقسم بترقيم لكل نموذج، وإخراج «أوراق» كما هو."""

import io
import json
import re
import zipfile
from collections import Counter

import pytest
from docx import Document
from lxml import etree

from apps.knowledge.services import load_all
from apps.papers import services as papers
from apps.papers.word import school
from apps.papers.word.builder import LOGO, build_docx

pytestmark = pytest.mark.django_db

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
FINAL = "g10-s1-2026-27-final"
PROFILE = {
    "school": "مدرسة الاختبار الثانوية",
    "teacher_name": "",
    "subject": "الرياضيات",
    "grade": "",
    "exam_minutes": 90,
    "exam_instructions": "",
    "worksheet_instructions": "",
}


def two_forms(**options) -> dict:
    load_all()
    a = papers.build_exam(FINAL, seed=7)
    b = papers.build_exam(FINAL, seed=a["seed"], form="B")
    return {"papers": [a, b], "profile": PROFILE, "template": "school", **options}


def all_text(doc) -> str:
    return "".join(doc.element.body.itertext())


def test_school_exam_fills_the_template_cover_and_frames_every_question():
    data = build_docx(two_forms(show_key=True))
    assert zipfile.ZipFile(io.BytesIO(data)).testzip() is None
    doc = Document(io.BytesIO(data))
    text = all_text(doc)
    assert not re.search(r"\{(school|exam|subject|year|minutes|total|grade|count_line)\}", text)
    for expected in (
        "مدرسة الاختبار الثانوية",
        "اختبار نهاية الفصل الأول (النموذج أ)",
        "اختبار نهاية الفصل الأول (النموذج ب)",
        "مادة الرياضيات للصف العاشر",
        "2026 / 2027",
        "ساعة ونصف",
        "10-",
        "تأكد من أن الاختبار مكون من 18 سؤالًا: 10 من أسئلة الاختيار من متعدد و8 من الأسئلة المقالية.",
        "المنسق / قائد الطاولة",
        "الآلات الحاسبة المسموح فيها",
        "انتهى الجزء الأول من الاختبار",
        "انتهت الأسئلة نرجو لكم التوفيق",
        "وضح خطوات الحل في المستطيل أدناه",
        "دليل تقدير الدرجات",  # المفتاح بإخراج «أوراق» بعد النموذجين
    ):
        assert expected in text, expected
    heads = Counter(
        t.text for t in doc.element.body.iter(f"{W}t") if t.text and t.text.startswith("السؤال رقم (")
    )
    assert heads == {f"السؤال رقم ({number})": 2 for number in range(1, 19)}  # مرة في كل نموذج
    # جدول الرصد: صف للموضوعي بمداه ومجموعه ثم صف لكل مقالي، والمجموع المعلن
    score = [t for t in doc.tables if "المراجع" in t.rows[0].cells[-1].text]
    assert len(score) == 2
    rows = [[c.text.strip() for c in row.cells[:2]] for row in score[0].rows]
    assert rows[1][0].strip("‎") == "1 – 10" and rows[1][1] == "20"
    assert [r[0] for r in rows[2:10]] == [str(n) for n in range(11, 19)]
    marks = {q["number"]: q["marks"] for q in two_forms()["papers"][0]["questions"]}
    assert [int(r[1]) for r in rows[2:10]] == [marks[n] for n in range(11, 19)]


def test_each_form_is_a_section_numbered_from_one_and_shape_ids_stay_unique():
    doc = Document(io.BytesIO(build_docx(two_forms(show_key=True))))
    assert len(doc.sections) == 3  # النموذجان والمفتاح
    for section in doc.sections:
        assert section._sectPr.find(f"{W}pgNumType").get(f"{W}start") == "1"
    for section in doc.sections:
        footer = etree.tostring(section.footer._element, encoding="unicode")
        assert "صفحة" in footer and 'w:instr=" SECTIONPAGES "' in footer
    ids = Counter(pr.get("id") for pr in doc.element.body.iter(f"{WP}docPr"))
    assert ids and max(ids.values()) == 1


def test_latin_options_are_left_to_right_because_the_template_style_loses_its_direction():
    doc = Document(io.BytesIO(build_docx(two_forms())))
    normal = doc.styles["Normal"].element.find(f"{W}pPr")
    assert normal is None or normal.find(f"{W}bidi") is None
    # فقرات الغلاف تحمل اتجاهها صريحًا فلا يتغير شكلها
    title = next(p for p in doc.element.body.iter(f"{W}p") if "تعليمات الاختبار" in "".join(p.itertext()))
    assert title.find(f"{W}pPr/{W}bidi") is not None


def test_cover_asset_is_the_template_cover_only():
    archive = zipfile.ZipFile(io.BytesIO(school.COVER))
    media = [name for name in archive.namelist() if name.startswith("word/media/")]
    assert 1 <= len(media) <= 2  # شعار الوزارة وحده
    assert not [name for name in archive.namelist() if name.startswith("customXml/")]
    text = all_text(Document(io.BytesIO(school.COVER)))
    assert "السؤال رقم" not in text and "{school}" in text and "{count_line}" in text


def test_default_template_and_worksheets_keep_the_platform_output():
    payload = two_forms()
    plain = build_docx({**payload, "template": "awraq"})
    assert "السؤال رقم (" not in all_text(Document(io.BytesIO(plain)))
    quiz = papers.build_quiz(["1.1"], seed=3, course="g10-s1")
    data = build_docx({"papers": [quiz], "profile": PROFILE, "template": "school"})
    archive = zipfile.ZipFile(io.BytesIO(data))
    media = [archive.read(n) for n in archive.namelist() if n.startswith("word/media/")]
    assert LOGO in media  # الاختبار القصير يبقى بإخراج «أوراق» وشعاره
    assert "السؤال رقم (" not in all_text(Document(io.BytesIO(data)))


def test_cover_helpers():
    assert school.grade_number("الصف العاشر") == "10"
    assert school.grade_number("الصف الثاني عشر") == "12"
    assert school.grade_number("الصف 11") == "11"
    assert school.count_line(10, 8).startswith("تأكد من أن الاختبار مكون من 18 سؤالًا")


def test_docx_api_accepts_only_known_templates(client):
    payload = two_forms()
    payload["papers"] = [payload["papers"][0]]
    ok = client.post("/api/v1/docx", json.dumps(payload), content_type="application/json")
    assert ok.status_code == 202, ok.content
    bad = client.post(
        "/api/v1/docx", json.dumps({**payload, "template": "other"}), content_type="application/json"
    )
    assert bad.status_code == 422
