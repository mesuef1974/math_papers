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


def test_question_head_is_one_line_and_stays_on_the_page_of_its_text():
    """الشريط فقرة واحدة في كل خلية (كانت فقرة فارغة قبل النص تجعله سطرين)، ويلحق بصف الجزء الأول،
    وكل جزء صف لا ينقسم بين صفحتين."""
    doc = Document(io.BytesIO(build_docx(two_forms())))
    frames = [t for t in doc.tables if t.rows[0].cells[0].text.startswith("السؤال رقم (")]
    assert len(frames) == 36
    paper = two_forms()["papers"][0]
    parts = {q["number"]: len(q["parts"]) for q in paper["questions"]}
    for table in frames:
        head = table.rows[0]._tr
        for tc in head.iter(f"{W}tc"):
            paragraphs = tc.findall(f"{W}p")
            assert len(paragraphs) == 1 and paragraphs[0].find(f"{W}pPr/{W}keepNext") is not None
        number = int(re.search(r"\((\d+)\)", table.rows[0].cells[0].text).group(1))
        body = table._tbl.findall(f"{W}tr")[1:]
        assert len(body) == parts[number]
        assert all(tr.find(f"{W}trPr/{W}cantSplit") is not None for tr in body)


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


def headers_of(doc) -> list[str]:
    return [t.text for t in doc.element.body.iter(f"{W}t") if t.text and t.text.startswith("السؤال رقم (")]


def test_school_worksheet_takes_the_template_header_only_and_frames_its_questions():
    load_all()
    sheet = papers.build_worksheet("1.1", 4, seed=3, course="g10-s1")
    data = build_docx({"papers": [sheet], "profile": PROFILE, "template": "school", "show_key": True})
    doc = Document(io.BytesIO(data))
    text = all_text(doc)
    assert not re.search(r"\{\w+\}", text)
    for expected in (
        "مدرسة الاختبار الثانوية",
        sheet["title"],
        "مادة الرياضيات للصف العاشر",
        school.WORKSHEET_INSTRUCTION,
    ):
        assert expected in text, expected
    # لا شيء من أجزاء الاختبار في الغلاف: الزمن والعام (لا عام في عنوانها) وجدول الرصد والتعليمات والمجموع
    for absent in ("زمن الاختبار", "العام الأكاديمي", "رقم السؤال", "المنسق", "تعليمات الاختبار", "الدرجة ("):
        assert absent not in text, absent
    assert headers_of(doc) == [f"السؤال رقم ({n})" for n in range(1, 5)]
    assert "وضح خطوات الحل في المستطيل أدناه" in text
    assert len(doc.sections) == 2  # الورقة والمفتاح، كل منهما مرقّم من 1
    assert all(s._sectPr.find(f"{W}pgNumType").get(f"{W}start") == "1" for s in doc.sections)


def test_teacher_worksheet_instructions_replace_the_default():
    load_all()
    sheet = papers.build_worksheet("1.1", 2, seed=3, course="g10-s1")
    profile = {**PROFILE, "worksheet_instructions": "حل في الدفتر"}
    text = all_text(
        Document(io.BytesIO(build_docx({"papers": [sheet], "profile": profile, "template": "school"})))
    )
    assert "حل في الدفتر" in text and school.WORKSHEET_INSTRUCTION not in text


def test_school_bundle_gives_each_worksheet_its_own_section_without_the_platform_cover():
    load_all()
    plan = [e for e in papers.bundle_plan(FINAL) if e["lesson"] in ("1.1", "1.2")]
    sheets = [papers.build_bundle_item(FINAL, e["lesson"], 9) for e in plan]
    payload = {
        "papers": sheets,
        "profile": PROFILE,
        "template": "school",
        "bundle": {"plan": plan, "seed": 9},
    }
    doc = Document(io.BytesIO(build_docx(payload)))
    assert len(doc.sections) == len(sheets) == 2
    text = all_text(doc)
    assert "رقم الحزمة" not in text and all(s["title"] in text for s in sheets)
    ids = Counter(pr.get("id") for pr in doc.element.body.iter(f"{WP}docPr"))
    assert max(ids.values()) == 1


def test_default_template_and_quizzes_keep_the_platform_output():
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
