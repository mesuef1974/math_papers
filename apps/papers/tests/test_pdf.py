"""PDF خادمي: المهمة والرمز الموقّع والملف، بمتصفح وهمي؛ Chromium الحقيقي يُجرَّب يدويًا في المعاينة."""

import json
import re
import time

import pytest
from django.core.cache import cache
from django.test import Client

from apps.core.models import AuditLog
from apps.papers import pdf
from apps.papers.access import ensure_teacher

FAKE_PDF = b"%PDF-1.4\nfake"


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def fake_browser(monkeypatch):
    """التنفيذ متزامن والمتصفح يقرأ الحمولة برمز الصفحة كما يفعل Chromium، ثم يعيد ملفًا ثابتًا."""
    seen = {}

    def render(url):
        token = url.rsplit("/print/", 1)[1]
        seen["url"] = url
        seen["payload"] = pdf.payload_for_token(token)
        assert seen["payload"] is not None
        return FAKE_PDF

    monkeypatch.setattr(pdf, "available", lambda: True)
    monkeypatch.setattr(pdf, "_submit", pdf._render_job)
    monkeypatch.setattr(pdf, "render_pdf", render)
    return seen


def payload(client, **options):
    paper = client.get("/api/v1/papers/worksheet", {"lesson": "1.2", "count": 3, "seed": 5}).json()
    profile = client.get("/api/v1/print-profile").json()
    return {"papers": [paper], "profile": profile, "date": "08/11/2026", "section": "12/3", **options}


def create(client, body):
    return client.post("/api/v1/pdf", json.dumps(body), content_type="application/json")


def test_job_renders_print_page_and_serves_file(client, fake_browser):
    res = create(client, payload(client, show_key=True))
    assert res.status_code == 202, res.content
    job = res.json()
    assert job["status"] == "done" and job["filename"].endswith(".pdf")
    assert fake_browser["url"].startswith(pdf.base_url() + "/print/")
    assert fake_browser["payload"]["show_key"] is True and fake_browser["payload"]["section"] == "12/3"
    assert client.get(f"/api/v1/pdf/{job['id']}").json()["status"] == "done"
    file = client.get(f"/api/v1/pdf/{job['id']}/file")
    assert file.status_code == 200 and file["Content-Type"] == "application/pdf"
    assert b"".join(file.streaming_content) == FAKE_PDF
    assert "filename*=utf-8''" in file["Content-Disposition"].lower()
    assert AuditLog.objects.filter(action="pdf.create", target=job["id"]).exists()


def test_other_teacher_cannot_see_job(client, fake_browser):
    job = create(client, payload(client)).json()
    other = Client()
    other.force_login(ensure_teacher("teacher2", "Rasm-Bayani-2026")[0])
    assert other.get(f"/api/v1/pdf/{job['id']}").status_code == 404
    assert other.get(f"/api/v1/pdf/{job['id']}/file").status_code == 404


def test_inline_pdf_is_framed_by_same_origin_only(client, fake_browser):
    """تبويب «صفحات PDF» يضمّن الملف في إطار من الأصل نفسه؛ التنزيل وWord وكل رد آخر يبقى ممنوع التضمين."""
    job = create(client, payload(client)).json()
    inline = client.get(f"/api/v1/pdf/{job['id']}/file", {"inline": 1})
    assert inline.status_code == 200 and inline["Content-Type"] == "application/pdf"
    assert inline["Content-Disposition"].startswith("inline")
    assert inline["X-Frame-Options"] == "SAMEORIGIN"
    assert inline["Content-Security-Policy"] == "frame-ancestors 'self'"
    assert b"".join(inline.streaming_content) == FAKE_PDF

    download = client.get(f"/api/v1/pdf/{job['id']}/file")
    assert download["Content-Disposition"].startswith("attachment")
    assert download["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in download["Content-Security-Policy"]
    status = client.get(f"/api/v1/pdf/{job['id']}")
    assert (
        status["X-Frame-Options"] == "DENY" and "frame-ancestors 'none'" in status["Content-Security-Policy"]
    )

    other = Client()
    other.force_login(ensure_teacher("teacher2", "Rasm-Bayani-2026")[0])
    assert other.get(f"/api/v1/pdf/{job['id']}/file", {"inline": 1}).status_code == 404


def test_inline_never_applies_to_word(client, monkeypatch):
    monkeypatch.setattr(pdf, "_submit", pdf._render_job)
    body = json.dumps(payload(client))
    job = client.post("/api/v1/docx", body, content_type="application/json").json()
    assert job["status"] == "done" and job["filename"].endswith(".docx")
    file = client.get(f"/api/v1/pdf/{job['id']}/file", {"inline": 1})
    assert file.status_code == 200
    assert file["Content-Disposition"].startswith("attachment")
    assert file["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in file["Content-Security-Policy"]


def test_print_payload_needs_valid_unexpired_token(client, fake_browser, monkeypatch):
    job = create(client, payload(client)).json()
    token = fake_browser["url"].rsplit("/print/", 1)[1]
    anonymous = Client()
    assert anonymous.get(f"/api/v1/pdf/print/{token}").status_code == 200
    assert anonymous.get(f"/api/v1/pdf/print/{token}x").status_code == 404
    assert anonymous.get("/api/v1/pdf/print/nonsense").status_code == 404
    monkeypatch.setattr(pdf, "TOKEN_MAX_AGE", -1)
    assert anonymous.get(f"/api/v1/pdf/print/{token}").status_code == 404
    assert client.get(f"/api/v1/pdf/{job['id']}").status_code == 200


def test_unavailable_server_says_so(client, monkeypatch):
    monkeypatch.setattr(pdf, "available", lambda: False)
    res = create(client, payload(client))
    assert res.status_code == 503 and "غير مفعّل" in res.json()["detail"]


def test_full_queue_rejects_and_leaves_nothing_behind(client, monkeypatch):
    monkeypatch.setattr(pdf, "available", lambda: True)
    monkeypatch.setattr(pdf, "_queued", pdf.MAX_QUEUE)
    res = create(client, payload(client))
    assert res.status_code == 429
    assert not [key for key in getattr(cache, "_cache", {}) if "papers:pdf" in key]


def test_export_job_left_running_by_its_test(client, monkeypatch):
    """يترك مهمة بطيئة في الخيط الخلفي بلا انتظار، كما يفعل كل اختبار يكتفي برد الإنشاء.
    الاختبار الذي يليه يتحقق أنها لم تعبر إليه."""
    from apps.papers.word import builder

    def slow(body):
        time.sleep(0.4)
        return b"PK-slow"

    monkeypatch.setattr(builder, "build_docx", slow)
    res = client.post("/api/v1/docx", json.dumps(payload(client)), content_type="application/json")
    assert res.status_code == 202 and res.json()["status"] in ("queued", "running")


def test_no_export_job_crosses_into_the_next_test(client):
    """الكاش مُسح قبل هذا الاختبار. مهمة باقية من الاختبار السابق كانت ستكتب حالتها وملفها بعد المسح،
    وهو ما أفشل test_full_queue_rejects_and_leaves_nothing_behind عشوائيًا في CI (2026-11-14)."""
    pdf._executor.submit(lambda: None).result(timeout=30)  # ينتظر ما قد يكون باقيًا في الخيط
    assert pdf._queued == 0
    assert not [key for key in getattr(cache, "_cache", {}) if "papers:pdf" in key]


def test_stale_and_failed_jobs_report_error(client, monkeypatch):
    monkeypatch.setattr(pdf, "available", lambda: True)
    monkeypatch.setattr(pdf, "_submit", lambda job_id: None)
    job = create(client, payload(client)).json()
    assert job["status"] == "queued"
    real_time = pdf.time.time
    monkeypatch.setattr(pdf.time, "time", lambda: real_time() + pdf.STALE_AFTER + 1)
    status = client.get(f"/api/v1/pdf/{job['id']}").json()
    assert status["status"] == "error" and status["error"] == pdf.FAILED
    assert client.get(f"/api/v1/pdf/{job['id']}/file").status_code == 404

    monkeypatch.setattr(pdf.time, "time", real_time)
    monkeypatch.setattr(pdf, "_submit", pdf._render_job)

    def boom(url):
        raise RuntimeError("chromium crashed")

    monkeypatch.setattr(pdf, "render_pdf", boom)
    failed = create(client, payload(client)).json()
    assert failed["status"] == "error" and failed["error"] == pdf.FAILED


def test_input_limits(client, fake_browser):
    body = payload(client)
    assert create(client, {**body, "papers": []}).status_code == 422
    assert create(client, {**body, "section": "x" * 41}).status_code == 422
    assert client.get("/api/v1/pdf/not-a-job").status_code == 422


def test_bundle_goes_through_with_its_index_and_many_papers_need_one(client, fake_browser):
    body = payload(client)
    paper = body["papers"][0]
    entry = {"lesson": "1.2", "title": "حساب النهايات", "count": 3, "levels": {"K": 1, "A": 1, "R": 1}}
    bundle = {"plan": [entry] * 3, "seed": 9}
    assert create(client, {**body, "papers": [paper] * 3}).status_code == 422  # أكثر من نموذجين بلا حزمة
    assert (
        create(client, {**body, "papers": [paper] * 3, "bundle": {"plan": [], "seed": 9}}).status_code == 422
    )
    res = create(client, {**body, "papers": [paper] * 3, "bundle": bundle})
    assert res.status_code == 202, res.content
    assert res.json()["filename"] == "حزمة أوراق العمل.pdf"
    seen = fake_browser["payload"]
    assert (
        len(seen["papers"]) == 3 and seen["bundle"]["seed"] == 9 and seen["bundle"]["plan"][0]["count"] == 3
    )
    token = fake_browser["url"].rsplit("/print/", 1)[1]
    printed = client.get(f"/api/v1/pdf/print/{token}").json()
    assert printed["bundle"]["plan"][0]["title"] == "حساب النهايات"
    assert create(client, body).status_code == 202 and fake_browser["payload"]["bundle"] is None


def test_safe_filename():
    assert pdf.safe_filename('اختبار: "الفصل" الأول/2026?') == "اختبار الفصل الأول 2026.pdf"
    assert pdf.safe_filename("   ") == "ورقة.pdf"
    assert re.fullmatch(r".{1,120}\.pdf", pdf.safe_filename("x" * 300))


def _pdf_with_pages(count: int) -> bytes:
    """ملف يشبه ما يكتبه Chromium: عقدة شجرة ‎/Pages‎ واحدة وكائن ‎/Type /Page‎ لكل صفحة."""
    kids = b"".join(b"%d 0 obj\n<< /Type /Page /Parent 1 0 R >>\nendobj\n" % (n + 3) for n in range(count))
    return b"%%PDF-1.4\n1 0 obj\n<< /Type /Pages /Count %d >>\nendobj\n" % count + kids + b"%EOF"


def test_count_pages_counts_page_objects_not_the_tree_node():
    assert pdf.count_pages(_pdf_with_pages(14)) == 14
    assert pdf.count_pages(_pdf_with_pages(1)) == 1
    assert pdf.count_pages(FAKE_PDF) == 0


def test_job_status_reports_pages_for_preview_flipping(client, fake_browser, monkeypatch):
    monkeypatch.setattr(pdf, "render_pdf", lambda url: _pdf_with_pages(3))
    job = create(client, payload(client)).json()
    assert client.get(f"/api/v1/pdf/{job['id']}").json()["pages"] == 3


def test_word_job_has_no_page_count(client, monkeypatch):
    monkeypatch.setattr(pdf, "_submit", pdf._render_job)
    job = client.post("/api/v1/docx", json.dumps(payload(client)), content_type="application/json").json()
    assert client.get(f"/api/v1/pdf/{job['id']}").json()["pages"] == 0
