"""تصدير Word: المعادلات OMML، رسم PNG، بنية الملف (اتجاه، خطوط، جداول)، ومسار الـAPI."""

import io
import json
import re
import struct
import zipfile

import pytest
from django.core.cache import cache
from docx import Document
from lxml import etree

from apps.core.models import AuditLog
from apps.papers.word import ooxml
from apps.papers.word.builder import (
    BRAND_LINE,
    BUNDLE_COVER_TITLE,
    LOGO,
    PATTERN_BAND,
    build_docx,
    marks_label,
    split_math,
    work_lines,
)
from apps.papers.word.graph_png import render_graph
from apps.papers.word.omml import split_array, to_omml

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


def parse(latex: str):
    return etree.fromstring(to_omml(latex))


def test_limit_fraction_and_scripts_become_native_omml():
    root = parse(r"\lim\limits_{x\to 1} \dfrac{x^{2}-1}{x-1}")
    assert root.find(f".//{M}limLow") is not None
    assert root.find(f".//{M}f") is not None
    assert root.find(f".//{M}sSup") is not None
    assert "→" in "".join(root.itertext())


def test_cases_and_delimiters_and_roots():
    cases = parse(r"f(x)=\begin{cases} 2x+1 & x<3 \\ 5 & x\ge 3 \end{cases}")
    assert len(cases.findall(f".//{M}mr")) == 2
    assert cases.find(f".//{M}d") is not None
    assert "≥" in "".join(cases.itertext())
    group = parse(r"\left(t - 4\right) \sqrt{x}")
    assert group.find(f".//{M}d") is not None and group.find(f".//{M}rad") is not None


def test_every_generated_formula_converts_to_well_formed_xml(client):
    for seed in (3, 11):
        slug = client.get("/api/v1/blueprints").json()[0]["slug"]
        paper = client.get("/api/v1/papers/exam", {"blueprint": slug, "seed": seed}).json()
        for question in paper["questions"]:
            for part in question["parts"]:
                for text in [part["stem"], part["answer"], *part["steps"], *part["options"]]:
                    for is_math, _, value in split_math(text):
                        if is_math and not split_array(value):
                            etree.fromstring(to_omml(value))


def test_value_table_is_split_out_of_the_formula():
    found = split_array(r"\begin{array}{c|cc} x & 1 & 2 \\ \hline f(x) & 3 & 4 \end{array}")
    assert found is not None
    _, table, _ = found
    assert table.rows == [["x", "1", "2"], ["f(x)", "3", "4"]]
    assert table.rules_above == [False, True]


def test_split_math_handles_literal_dollar_and_unclosed():
    assert split_math(r"سعر \$5 و $x$") == [(False, False, "سعر $5 و "), (True, False, "x")]
    assert split_math("نص $غير مغلق") == [(False, False, "نص $غير مغلق")]


def test_marks_label_arabic_plurals():
    assert [marks_label(n) for n in (1, 2, 5, 12)] == ["درجة واحدة", "درجتان", "5 درجات", "12 درجة"]


def test_graph_png_is_valid_png_with_expected_aspect():
    graph = {
        "window": [-4, 4, -3, 3],
        "label": "f",
        "curves": [[[-3, 2], [0, 0], [3, 2]]],
        "dots": [[0, 0, True]],
        "asymptotes": [],
        "lines": [],
    }
    png, width, height = render_graph(graph)
    assert png.startswith(b"\x89PNG") and width == 8 * 26 + 44 and height == 6 * 26 + 44


PROFILE = {
    "school": "مدرسة",
    "teacher_name": "معلم",
    "subject": "الرياضيات",
    "grade": "الصف 12: المسار العلمي",
    "exam_minutes": 150,
    "exam_instructions": "",
    "worksheet_instructions": "حل المسائل",
}


def sample_payload(client, kind="exam", **options):
    if kind == "exam":
        slug = client.get("/api/v1/blueprints").json()[0]["slug"]
        paper = client.get("/api/v1/papers/exam", {"blueprint": slug, "seed": 11}).json()
    else:
        paper = client.get("/api/v1/papers/worksheet", {"lesson": "3.1", "count": 4, "seed": 5}).json()
    return {"papers": [paper], "profile": PROFILE, "date": "11/11/2026", "section": "12/3", **options}


def test_exam_docx_structure(client):
    data = build_docx({**sample_payload(client, show_key=True, bubble=True)})
    assert zipfile.ZipFile(io.BytesIO(data)).testzip() is None
    doc = Document(io.BytesIO(data))
    body = doc.element.body
    assert body.find(f".//{M}oMath") is not None  # معادلات أصلية
    assert body.find(f".//{W}drawing") is not None  # رسوم PNG
    assert doc.sections[0]._sectPr.find(f"{W}bidi") is not None  # صفحة RTL
    text = "\n".join(p.text for p in doc.paragraphs) + "\n".join(
        cell.text for table in doc.tables for row in table.rows for cell in row.cells
    )
    for expected in (
        "اختبار الرياضيات",
        "تعليمات عامة",
        "General instructions",
        "جدول رصد الدرجات",
        "دليل تقدير الدرجات",
        "ورقة الإجابة",
        "A.",
        "D.",
    ):
        assert expected in text
    assert "الصف: الصف" not in text and "الصف 12" in text
    assert all(t._tbl.find(f"{W}tblPr/{W}bidiVisual") is not None for t in doc.tables[:1])


def test_worksheet_docx_has_header_and_key(client):
    data = build_docx(sample_payload(client, "worksheet", show_key=True))
    doc = Document(io.BytesIO(data))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "السؤال 1" in text and "انتهت الأسئلة" in "".join(
        cell.text for table in doc.tables for row in table.rows for cell in row.cells
    )
    assert any("مفتاح الحل" in cell.text for table in doc.tables for row in table.rows for cell in row.cells)


def test_key_marks_column_only_when_the_paper_has_marks(client):
    def key_heads(kind):
        doc = Document(io.BytesIO(build_docx(sample_payload(client, kind, show_key=True))))
        for table in doc.tables:
            heads = [cell.text for cell in table.rows[0].cells]
            if heads[:2] == ["السؤال", "الإجابة والخطوات"]:
                return heads, [cell.text for cell in table.rows[1].cells]
        raise AssertionError("لا جدول حلول في الوثيقة")

    heads, first = key_heads("worksheet")  # ورقة العمل بلا درجات: لا عمود فارغ
    assert heads == ["السؤال", "الإجابة والخطوات", "الدرس", "المستوى"] and len(first) == 4
    heads, first = key_heads("exam")
    assert heads[2] == "الدرجة" and heads[-1] == "المجموع" and first[-1].strip().isdigit()


def test_key_distributes_essay_marks_over_steps_and_final_answer(client):
    """جدول الحلول في Word: مجموع درجات بنود كل جزء يساوي مجموعه، ولكل جزء مقالي بند جواب نهائي واحد."""
    payload = sample_payload(client, show_key=True)
    doc = Document(io.BytesIO(build_docx(payload)))
    table = next(
        t for t in doc.tables if [c.text for c in t.rows[0].cells][:2] == ["السؤال", "الإجابة والخطوات"]
    )
    sums: dict[str, float] = {}
    totals: dict[str, float] = {}
    finals: dict[str, int] = {}
    for row in table.rows[1:]:
        cells = row.cells  # الخلايا المدموجة رأسيًا تعيد نص أول صف في الجزء
        label = cells[0].text
        sums[label] = sums.get(label, 0) + float(cells[2].text)
        totals[label] = float(cells[5].text)
        finals[label] = finals.get(label, 0) + cells[1].text.startswith("الجواب النهائي")
    assert sums == totals
    essay = [
        f"{q['number']} {p['label']}".strip()
        for q in payload["papers"][0]["questions"]
        if q["kind"] == "essay"
        for p in q["parts"]
    ]
    assert essay and all(finals[label] == 1 for label in essay)
    assert all(count == 0 for label, count in finals.items() if label not in essay)
    assert b'<w:vMerge w:val="restart"/>' in parts_of(build_docx(payload))["word/document.xml"]
    # بنود الجزء الواحد لا تنقسم بين صفحتين: كل صف غير أخير في جزئه يلحق بما بعده، بكل فقراته
    rows = table.rows[1:]
    for row, following in zip(rows, rows[1:], strict=False):
        kept = all(p.find(f"{W}pPr/{W}keepNext") is not None for p in row._tr.iter(f"{W}p"))
        assert kept == (row.cells[0].text == following.cells[0].text)


def test_two_forms_make_two_sections(client):
    payload = sample_payload(client, "worksheet")
    payload["papers"] = [payload["papers"][0], {**payload["papers"][0], "form": "B"}]
    doc = Document(io.BytesIO(build_docx(payload)))
    assert len(doc.sections) == 2


def create(client, body):
    return client.post("/api/v1/docx", json.dumps(body), content_type="application/json")


def test_docx_job_serves_word_file_and_audits(client):
    res = create(client, sample_payload(client, "worksheet"))
    assert res.status_code == 202, res.content
    job = res.json()
    assert job["filename"].endswith(".docx")
    # التنفيذ في خيط خلفي؛ ننتظر انتهاءه
    import time

    for _ in range(100):
        status = client.get(f"/api/v1/pdf/{job['id']}").json()
        if status["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert status["status"] == "done", status
    file = client.get(f"/api/v1/pdf/{job['id']}/file")
    assert file.status_code == 200 and "wordprocessingml" in file["Content-Type"]
    assert b"".join(file.streaming_content)[:2] == b"PK"
    assert AuditLog.objects.filter(action="docx.create", target=job["id"]).exists()


def test_docx_needs_login():
    from django.test import Client

    assert Client().post("/api/v1/docx", "{}", content_type="application/json").status_code in (401, 403)


# ---------- الهوية والتخطيط والحزمة ----------


def parts_of(data: bytes) -> dict[str, bytes]:
    archive = zipfile.ZipFile(io.BytesIO(data))
    return {name: archive.read(name) for name in archive.namelist()}


def bundle_payload(client, lessons=("1.1", "1.2", "3.1"), **options):
    slug = client.get("/api/v1/blueprints").json()[0]["slug"]
    plan = [
        entry
        for entry in client.get("/api/v1/papers/bundle-plan", {"blueprint": slug}).json()
        if entry["lesson"] in lessons
    ]
    papers = [
        client.get("/api/v1/papers/bundle-item", {"blueprint": slug, "lesson": e["lesson"], "seed": 9}).json()
        for e in plan
    ]
    return {
        "papers": papers,
        "profile": PROFILE,
        "date": "12/11/2026",
        "section": "12/3",
        "bundle": {"plan": plan, "seed": 9},
        **options,
    }


@pytest.mark.parametrize("kind", ["exam", "worksheet"])
def test_every_document_carries_platform_logo_and_name(client, kind):
    files = parts_of(build_docx(sample_payload(client, kind, show_key=True)))
    assert LOGO in [data for name, data in files.items() if name.startswith("word/media/")]
    footers = [data.decode("utf-8") for name, data in files.items() if name.startswith("word/footer")]
    assert footers and all(BRAND_LINE in footer for footer in footers)
    assert all(" PAGE " in footer and " NUMPAGES " in footer for footer in footers)


def test_exam_cover_opens_with_pattern_band_before_the_logo(client):
    """النمط على الغلاف فقط (الدليل: الأغلفة)، وفوق الشعار لا بجواره؛ وورقة العمل بلا غلاف فلا نمط فيها."""
    exam = parts_of(build_docx(sample_payload(client, "exam")))
    media = {name: data for name, data in exam.items() if name.startswith("word/media/")}
    assert PATTERN_BAND in media.values() and LOGO in media.values()
    document = exam["word/document.xml"].decode("utf-8")
    ids = {data: name.rsplit("/", 1)[1] for name, data in media.items()}
    rels = exam["word/_rels/document.xml.rels"].decode("utf-8")
    order = re.findall(r'r:embed="(rId\d+)"', document)
    target = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="media/([^"]+)"', rels))
    target.update({rid: t for t, rid in re.findall(r'Target="media/([^"]+)"[^>]*Id="(rId\d+)"', rels)})
    first_two = [target.get(rid) for rid in order[:2]]
    assert first_two == [ids[PATTERN_BAND], ids[LOGO]]
    sheet = parts_of(build_docx(sample_payload(client, "worksheet")))
    assert PATTERN_BAND not in [d for n, d in sheet.items() if n.startswith("word/media/")]


def test_worksheet_layout_badge_ruled_lines_and_graph_beside_them(client):
    paper = client.get("/api/v1/papers/worksheet", {"lesson": "3.1", "count": 8, "seed": 5}).json()
    assert any(part["graph"] for q in paper["questions"] for part in q["parts"])
    payload = {"papers": [paper], "profile": PROFILE, "date": "12/11/2026", "section": "12/3"}
    doc = Document(io.BytesIO(build_docx(payload)))
    body = doc.element.body
    badge = next(r for r in body.iter(f"{W}r") if "السؤال 1" in "".join(r.itertext()))
    assert badge.find(f"{W}rPr/{W}shd").get(f"{W}fill") == ooxml.BRAND  # شارة بلون الهوية
    assert body.find(f".//{W}tcBorders/{W}bottom[@{W}val='dotted']") is not None
    assert body.find(f".//{W}tcBorders/{W}bottom[@{W}val='dashed']") is None
    # الرسم في خلية مدموجة رأسيًا بجوار أسطر الحل، داخل جدول واحد
    merged = body.find(f".//{W}tcPr/{W}vMerge[@{W}val='restart']")
    assert merged is not None and merged.getparent().getparent().find(f".//{W}drawing") is not None
    # رقم الشعبة في تشغيل غير عربي فلا يقلب Word «12/3»
    section = next(r for r in body.iter(f"{W}r") if r.findtext(f"{W}t") == "12/3")
    assert section.find(f"{W}rPr/{W}rtl") is None


def test_work_lines_follow_marks_and_fill_beside_a_graph():
    assert work_lines({"marks": 0}) == 4 and work_lines({"marks": 1}) == 3
    assert work_lines({"marks": 3}) == 4 and work_lines({"marks": 9}) == 6
    assert work_lines({"marks": 0, "graph": {"window": [0, 1, 0, 1]}}) == 6


def test_alignment_is_physical_in_arabic_paragraphs():
    doc = Document()
    arabic = ooxml.new_paragraph(doc, align="left")
    latin = ooxml.new_paragraph(doc, rtl=False, align="left")
    assert arabic._p.find(f"{W}pPr/{W}jc").get(f"{W}val") == "right"  # Word يعكسها في فقرة bidi
    assert latin._p.find(f"{W}pPr/{W}jc").get(f"{W}val") == "left"


def test_bundle_docx_has_cover_index_every_sheet_and_keys_last(client):
    payload = bundle_payload(client)
    doc = Document(io.BytesIO(build_docx(payload)))
    assert len(doc.sections) == 1
    cells = [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
    text = "\n".join(p.text for p in doc.paragraphs) + "\n".join(cells)
    assert BUNDLE_COVER_TITLE in text and "الفهرس" in text and "رقم الحزمة 9" in text
    for entry, paper in zip(payload["bundle"]["plan"], payload["papers"], strict=True):
        assert entry["title"] in cells and entry["lesson"] in cells
        assert paper["title"] in cells
    assert "النموذج" not in cells  # الحزمة ليست نماذج أ/ب: لا خانة «النموذج» في الترويسات
    assert cells.count("انتهت الأسئلة") == len(payload["papers"])
    footer = parts_of(build_docx(payload))["word/footer1.xml"].decode("utf-8")
    assert BUNDLE_COVER_TITLE in footer
    keyed = Document(io.BytesIO(build_docx({**payload, "show_key": True})))
    assert len(keyed.sections) == 2
    keys = [c.text for t in keyed.tables for r in t.rows for c in r.cells if c.text.startswith("مفتاح الحل")]
    assert len(keys) == len(payload["papers"])


def test_docx_api_accepts_bundle_and_names_the_file(client):
    res = create(client, bundle_payload(client))
    assert res.status_code == 202, res.content
    assert res.json()["filename"] == "حزمة أوراق العمل.docx"


def test_documents_follow_brand_colors(client):
    """ألوان الهوية في Word: عنوان الترويسة وخطها بالعنابي، ترويسات الجداول عنابية بنص أبيض، والشعار ملوّن."""
    data = build_docx(sample_payload(client, "worksheet", show_key=True))
    doc = Document(io.BytesIO(data))
    body = doc.element.body
    title = next(r for r in body.iter(f"{W}r") if (r.findtext(f"{W}t") or "").startswith("ورقة عمل"))
    assert title.find(f"{W}rPr/{W}color").get(f"{W}val") == ooxml.BRAND_STRONG
    rules = [b.get(f"{W}color") for b in body.iter(f"{W}bottom") if b.getparent().tag == f"{W}pBdr"]
    assert ooxml.BRAND in rules  # خط الترويسة السميك
    heads = [
        tc
        for tc in body.iter(f"{W}tc")
        if tc.find(f"{W}tcPr/{W}shd") is not None
        and tc.find(f"{W}tcPr/{W}shd").get(f"{W}fill") == ooxml.BRAND
    ]
    assert heads and all(
        r.find(f"{W}rPr/{W}color").get(f"{W}val") == ooxml.WHITE for tc in heads for r in tc.iter(f"{W}r")
    )
    footer = parts_of(data)["word/footer1.xml"].decode("utf-8")
    assert f'w:color="{ooxml.BRAND}"' in footer
    assert struct.unpack(">B", LOGO[25:26])[0] in (2, 3, 6)  # PNG ملوّن (RGB أو لوحة ألوان)، لا أحادي


def test_paper_font_is_embedded_and_is_the_print_font(client):
    """خط الورقة واحد في الطباعة وPDF وWord، ومضمَّن في الملف فيظهر على جهاز لا يملكه."""
    files = parts_of(build_docx(sample_payload(client, "worksheet")))
    table = files["word/fontTable.xml"].decode("utf-8")
    rels = files["word/_rels/fontTable.xml.rels"].decode("utf-8")
    assert sorted(n for n in files if n.startswith("word/fonts/")) == [
        "word/fonts/font1.odttf",
        "word/fonts/font2.odttf",
    ]
    for index, (tag, (filename, key)) in enumerate(ooxml.EMBEDDED_FONTS.items(), start=1):
        original = (ooxml.FONT_DIR / filename).read_bytes()
        embedded = files[f"word/fonts/font{index}.odttf"]
        assert original[:4] == b"\x00\x01\x00\x00"  # ملف TrueType
        assert embedded != original and ooxml.obfuscate_font(embedded, key) == original  # معمًّى ويعود كما كان
        assert f"<w:{tag} " in table and f'w:fontKey="{key}"' in table
        assert f"fonts/font{index}.odttf" in rels
    assert f'w:name="{ooxml.FONT}"' in table
    assert ooxml.OBFUSCATED_FONT in files["[Content_Types].xml"].decode("utf-8")
    assert "<w:embedTrueTypeFonts" in files["word/settings.xml"].decode("utf-8")
    document = files["word/document.xml"].decode("utf-8")
    assert f'w:cs="{ooxml.FONT}"' in document and 'w:cs="Arial"' not in document
    tokens = (ooxml.FONT_DIR.parents[4] / "frontend" / "src" / "styles" / "tokens.css").read_text(
        encoding="utf-8"
    )
    assert f'--font-print: "{ooxml.FONT}"' in tokens


def _font_table(data: bytes, tag: bytes) -> bytes:
    count = struct.unpack(">H", data[4:6])[0]
    for index in range(count):
        name, _, offset, length = struct.unpack(">4sLLL", data[12 + 16 * index : 28 + 16 * index])
        if name == tag:
            return data[offset : offset + length]
    raise KeyError(tag)


def test_word_line_height_is_the_print_line_height(client):
    """Word يقيس السطر بارتفاع الخط الطبيعي لا بحجمه؛ المضاعف يعيده إلى ارتفاع سطر الطباعة."""
    for filename, _ in ooxml.EMBEDDED_FONTS.values():
        font = (ooxml.FONT_DIR / filename).read_bytes()
        units = struct.unpack(">H", _font_table(font, b"head")[18:20])[0]
        os2 = _font_table(font, b"OS/2")
        ascent, descent, gap = struct.unpack(">hhh", os2[68:74])
        assert struct.unpack(">H", os2[62:64])[0] & 0x80  # USE_TYPO_METRICS: Word يأخذ مقاييس typo
        assert (ascent - descent + gap) / units == pytest.approx(ooxml.FONT_NATURAL_LINE, abs=0.001)
    css = (ooxml.FONT_DIR.parents[4] / "frontend" / "src" / "styles" / "print.css").read_text(
        encoding="utf-8"
    )
    assert f"--leading-body: {ooxml.PRINT_LEADING};" in css
    assert ooxml.LINE_MULTIPLE * ooxml.FONT_NATURAL_LINE == pytest.approx(ooxml.PRINT_LEADING, abs=0.005)
    document = parts_of(build_docx(sample_payload(client, "worksheet")))["word/document.xml"].decode("utf-8")
    assert f'w:line="{round(ooxml.LINE_MULTIPLE * 240)}" w:lineRule="auto"' in document
    assert 'w:line="276"' not in document  # مضاعف Arial القديم
