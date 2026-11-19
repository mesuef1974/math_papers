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
    ):
        assert expected in text, expected
    assert "دليل تقدير الدرجات" not in text  # المفتاح ملف مستقل (key_only) ولو طُلب show_key
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
    assert len(doc.sections) == 2  # النموذجان؛ المفتاح ملف مستقل
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


def option_paragraphs(doc) -> dict[str, list]:
    """فقرة قيمة كل بديل (الخلية الثانية في جدول البديل المتداخل) بنصها المكتوب."""
    found: dict[str, list] = {}
    for tbl in doc.element.body.iter(f"{W}tbl"):
        if tbl.find(f"{W}tblPr/{W}tblBorders") is not None:
            continue
        rows = tbl.findall(f"{W}tr")
        cells = rows[0].findall(f"{W}tc") if len(rows) == 1 else []
        if len(cells) != 2 or "".join(t.text for t in cells[0].iter(f"{W}t")) not in set("ABCD"):
            continue
        paragraph = cells[1].find(f"{W}p")
        # نص المعادلات في m:t
        text = "".join(t.text or "" for t in paragraph.iter() if t.tag.endswith("}t")).strip()
        found.setdefault(text, []).append(paragraph)
    return found


def test_arabic_options_read_right_to_left_and_latin_ones_left_to_right():
    """«$4$ ساعات» في فقرة لاتينية كان يُقرأ «ساعات 4»: البديل الذي فيه كلام عربي فقرته عربية، والرياضي لاتينية."""
    assert school.arabic_option("$4$ ساعات") and school.arabic_option("تطابق زاويتين (AA)")
    assert not school.arabic_option("$x=-3\\pm\\sqrt{3}$") and not school.arabic_option("$]4,8[$")
    options = option_paragraphs(Document(io.BytesIO(build_docx(two_forms()))))
    arabic = [p for text, ps in options.items() if "ساعات" in text for p in ps]
    latin = [p for text, ps in options.items() if text and not re.search("[؀-ۿ]", text) for p in ps]
    assert arabic and latin
    assert all(p.find(f"{W}pPr/{W}bidi") is not None for p in arabic)
    assert all(p.find(f"{W}pPr/{W}bidi") is None for p in latin)


def test_nested_option_tables_add_no_blank_lines():
    """الجدول المتداخل كان بين فقرتين فارغتين بارتفاع سطر، فكان البديل ثلاثة أسطر وإطار السؤال نصف صفحة:
    الخلية تبدأ بجدولها، والفقرة التي يشترطها Word بعده بارتفاع نقطة."""
    doc = Document(io.BytesIO(build_docx(two_forms())))
    nested = [tbl for tbl in doc.element.body.iter(f"{W}tbl") if tbl.getparent().tag == f"{W}tc"]
    assert nested
    for tbl in nested:
        previous = tbl.getprevious()
        assert previous is None or previous.tag != f"{W}p" or "".join(previous.itertext()).strip()
        after = tbl.getnext()
        spacing = after.find(f"{W}pPr/{W}spacing")
        assert (
            after.tag == f"{W}p"
            and spacing.get(f"{W}lineRule") == "exact"
            and spacing.get(f"{W}line") == "20"
        )


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
    assert len(doc.sections) == 1 and "مفتاح الحل" not in text  # المفتاح ملف مستقل
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
    # عبارة الختام مرة واحدة بعد آخر ورقة، لا في آخر كل ورقة
    # عناصر w:t لا itertext (يكرر نص الشوط في عناصر python-docx)
    runs = [t.text or "" for t in doc.element.body.iter(f"{W}t")]
    closing = [i for i, t in enumerate(runs) if t == school.CLOSING]
    assert len(closing) == 1
    assert closing[0] > max(i for i, t in enumerate(runs) if sheets[-1]["title"] in t)
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


def test_key_only_file_has_the_template_header_and_the_key_of_each_form_without_questions():
    doc = Document(io.BytesIO(build_docx(two_forms(key_only=True))))
    text = all_text(doc)
    assert not re.search(r"\{\w+\}", text)
    for expected in (
        "مدرسة الاختبار الثانوية",
        "دليل تقدير الدرجات: اختبار نهاية الفصل الأول (النموذج أ)",
        "دليل تقدير الدرجات: اختبار نهاية الفصل الأول (النموذج ب)",
        "مادة الرياضيات للصف العاشر",
        "إجابات الأسئلة الموضوعية",
        "الحلول والخطوات بدرجاتها",
    ):
        assert expected in text, expected
    # لا أسئلة ولا غلاف الاختبار ولا ترويسة «أوراق» المكررة
    assert headers_of(doc) == []
    for absent in ("المراجع", "المنسق", "زمن الاختبار", school.CLOSING):
        assert absent not in text, absent
    assert len(doc.sections) == 2  # قسم بترقيمه لكل نموذج
    assert all(s._sectPr.find(f"{W}pgNumType").get(f"{W}start") == "1" for s in doc.sections)
    ids = Counter(pr.get("id") for pr in doc.element.body.iter(f"{WP}docPr"))
    assert max(ids.values()) == 1


def test_key_only_worksheet_bundle_gives_each_key_the_template_header():
    load_all()
    plan = [e for e in papers.bundle_plan(FINAL) if e["lesson"] in ("1.1", "1.2")]
    sheets = [papers.build_bundle_item(FINAL, e["lesson"], 9) for e in plan]
    payload = {
        "papers": sheets,
        "profile": PROFILE,
        "template": "school",
        "key_only": True,
        "bundle": {"plan": plan, "seed": 9},
    }
    doc = Document(io.BytesIO(build_docx(payload)))
    text = all_text(doc)
    assert len(doc.sections) == 2 and headers_of(doc) == []
    assert all(f"مفتاح الحل: {s['title']}" in text for s in sheets)
    assert "رقم الحزمة" not in text


def test_docx_api_names_the_key_file_and_rejects_key_only_outside_the_school_template(client):
    payload = two_forms(key_only=True)
    payload["papers"] = [payload["papers"][0]]
    ok = client.post("/api/v1/docx", json.dumps(payload), content_type="application/json")
    assert ok.status_code == 202, ok.content
    assert ok.json()["filename"].startswith("مفتاح")
    bad = client.post(
        "/api/v1/docx", json.dumps({**payload, "template": "awraq"}), content_type="application/json"
    )
    assert bad.status_code == 422


def test_key_only_file_has_page_example_and_exercise_columns_from_the_source_itself():
    """المفتاح المستقل بقالب المدرسة فيه أعمدة «الصفحة» و«المثال» و«التدريب» لكل سؤال، موضوعيًا كان أو مقاليًا،
    مشتقة من أرقام المصدر في Word نفسه: الحمولة هنا بلا نص مشتق (source_label) ولا تغيب الأعمدة."""
    payload = two_forms(key_only=True)
    paper = payload["papers"][0]
    assert all("source_label" not in p for q in paper["questions"] for p in q["parts"])
    doc = Document(io.BytesIO(build_docx(payload)))
    table = next(t for t in doc.tables if t.rows[0].cells[0].text == "السؤال")
    heads = [c.text for c in table.rows[0].cells]
    assert heads[3:7] == ["الدرس", "الصفحة", "المثال", "التدريب"]
    rows = {}
    for row in table.rows[1:]:
        rows.setdefault(row.cells[0].text, tuple(re.sub("[‎‏]", "", row.cells[c].text) for c in (4, 5, 6)))
    first = paper["questions"][0]["parts"][0]["source"]
    assert rows["1"][:2] == (str(first["page"]), str(first["number"]))
    assert len({key.split()[0] for key in rows}) == len(paper["questions"])
    assert all(page.isdigit() and example.isdigit() for page, example, _ in rows.values())


def _keeps_next(element) -> bool:
    paragraphs = [element] if element.tag == f"{W}p" else list(element.iter(f"{W}p"))
    return all(p.find(f"{W}pPr/{W}keepNext") is not None for p in paragraphs)


def test_essay_instructions_stay_on_the_page_of_the_first_essay_question():
    """تعليمات الأسئلة المقالية والسؤال 11 في صفحة واحدة: مربع التعليمات والفاصل بعده يلحقان بشريط السؤال،
    والشريط يلحق بصف جزئه الأول. وكذلك تعليمات الموضوعي مع السؤال 1."""
    doc = Document(io.BytesIO(build_docx(two_forms())))
    body = list(doc.element.body)
    for lead in ("عند الإجابة على الأسئلة من 11", "اختر الإجابة الصحيحة لكل من الأسئلة من 1 "):
        index = next(i for i, e in enumerate(body) if e.tag == f"{W}tbl" and lead in "".join(e.itertext()))
        box, gap, question = body[index], body[index + 1], body[index + 2]
        assert _keeps_next(box) and _keeps_next(gap), lead
        head = question.find(f"{W}tr")
        assert "السؤال رقم" in "".join(head.itertext()) and _keeps_next(head), lead


FORECAST = "g12-sci-s1-2026-27-forecast"


def test_key_only_file_keeps_the_source_columns_for_every_course_even_without_sources():
    """مفتاح قالب المدرسة بأعمدة «الصفحة» و«المثال» و«التدريب» لكل مقرر: صيغ الثاني عشر برقم مثالها وصفحته وبلا
    تدريب بعد (الروابط تنتظر اعتماد المالك)، فتبقى الأعمدة بأرقامها وخانة التدريب «—» لا مخترعة (قرار المالك 2026-11-19)."""
    load_all()
    a = papers.build_exam(FORECAST, seed=7)
    sources = [p.get("source") for q in a["questions"] for p in q["parts"]]
    assert all(s and s["number"] and s.get("page") for s in sources)
    assert not any(s.get("exercises") for s in sources)
    doc = Document(
        io.BytesIO(build_docx({"papers": [a], "profile": PROFILE, "template": "school", "key_only": True}))
    )
    table = next(t for t in doc.tables if t.rows[0].cells[0].text == "السؤال")
    assert [c.text for c in table.rows[0].cells][3:7] == ["الدرس", "الصفحة", "المثال", "التدريب"]
    row = table.rows[1].cells
    assert row[4].text.isdigit() and row[5].text.isdigit()
    assert row[6].text == "—"


def _has_keep(element) -> bool:
    return element.find(f".//{W}keepNext") is not None


@pytest.mark.parametrize("slug", [FINAL, FORECAST])
def test_question_frames_stay_whole_when_they_fit_and_break_between_parts_when_longer(slug):
    """لكل مقرر: السؤال الذي تتسع له صفحة كل صف فيه عدا الأخير يلحق بما بعده (كل فقراته)، فلا ينقسم. والأطول من
    صفحة (مقاليات الثاني عشر) لا فقرة تلحق بالتالي في صفوف أجزائه، لأن Word يربط الصف بفقرة واحدة فيه فيدفع السؤال
    كله إلى صفحة جديدة ويترك التعليمات وحدها. وفي الحالين الشريط يلحق بالجزء الأول، والتعليمات بالسؤال بعدها."""
    load_all()
    a = papers.build_exam(slug, seed=7)
    doc = Document(io.BytesIO(build_docx({"papers": [a], "profile": PROFILE, "template": "school"})))
    body = list(doc.element.body)
    frames = [e for e in body if e.tag == f"{W}tbl" and "السؤال رقم" in "".join(e.itertext())]
    assert len(frames) == len(a["questions"])
    released = 0
    for frame in frames:
        rows = frame.findall(f"{W}tr")
        assert _keeps_next(rows[0]) and not _keeps_next(rows[-1])
        if all(_keeps_next(row) for row in rows[:-1]):
            continue
        assert not any(_has_keep(row) for row in rows[1:]), "".join(rows[0].itertext())
        released += 1
    assert released == (3 if slug == FORECAST else 0)
    for index, element in enumerate(body):
        if element.tag == f"{W}tbl" and "".join(element.itertext()).startswith("تعليمات"):
            assert _keeps_next(element) and _keeps_next(body[index + 1])
            assert body[index + 2] in frames
