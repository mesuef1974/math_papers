"""تصدير Word: المعادلات OMML، رسم PNG، بنية الملف (اتجاه، خطوط، جداول)، ومسار الـAPI."""

import io
import json
import zipfile

import pytest
from django.core.cache import cache
from docx import Document
from lxml import etree

from apps.core.models import AuditLog
from apps.papers.word.builder import build_docx, marks_label, split_math
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
