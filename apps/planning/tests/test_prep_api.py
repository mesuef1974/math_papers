"""التحضير للمعلم (المرحلة 3 من docs/lesson_prep_plan.md): المسار خلف TeacherAuth، وWord بنموذج الوزارة لكل حصة من الـ48.

أهداف الوحدة المعتمدة (prep/unit-<n>.json) تظهر نصوصها ونتاجات معاييرها؛ وما لم يُعتمد يظهر وصفًا بعلامة «معلَّق»
في الرد وفي ملف Word (قرار المالك 2026-11-19).
"""

import re
import zipfile
from io import BytesIO

import pytest
from docx import Document

from apps.core.models import AuditLog
from apps.curriculum.courses import GRADE10_SLUG
from apps.knowledge.domain.unit_prep import approved_standards, unit_prep
from apps.planning.domain.prep_sheet import PENDING_MARK, split_minutes
from apps.planning.prep_word import TEACH_ROW

API = "/api/v1/preps"
TOKEN = re.compile(r"\{[a-z_]+\}")

pytestmark = pytest.mark.usefixtures("loaded_courses")


def document_text(data: bytes) -> str:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml = "".join(
            archive.read(n).decode()
            for n in archive.namelist()
            if re.match(r"word/(document|footer\d|header\d)\.xml", n)
        )
    return "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))


def test_split_minutes_sums_to_total_with_extra_first():
    assert split_minutes(23, 3) == [8, 8, 7]
    assert split_minutes(11, 1) == [11]
    assert split_minutes(5, 0) == []


PATHS = (f"{API}/{GRADE10_SLUG}", f"{API}/{GRADE10_SLUG}/1.1/1", f"{API}/{GRADE10_SLUG}/1.1/1/word")


@pytest.mark.django_db
@pytest.mark.parametrize("path", PATHS)
def test_preps_require_a_session(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("path", PATHS)
def test_preps_require_the_teacher_permission(outsider_client, path):
    assert outsider_client.get(path).status_code == 403


@pytest.mark.django_db
def test_unknown_course_or_period_is_404(teacher_client):
    assert teacher_client.get(f"{API}/no-such-course").status_code == 404
    assert teacher_client.get(f"{API}/{GRADE10_SLUG}/1.1/99").status_code == 404
    assert teacher_client.get(f"{API}/{GRADE10_SLUG}/9.9/1/word").status_code == 404


@pytest.mark.django_db
def test_every_lesson_period_opens_and_downloads_in_the_ministry_template(teacher_client):
    periods = teacher_client.get(f"{API}/{GRADE10_SLUG}").json()
    assert len(periods) == 48
    assert {p["status"] for p in periods} <= {"pass", "pending", "fail"}
    for period in periods:
        base = f"{API}/{GRADE10_SLUG}/{period['lesson']}/{period['k']}"
        sheet = teacher_client.get(base).json()
        assert (sheet["lesson"], sheet["k"], sheet["n"]) == (period["lesson"], period["k"], period["n"])
        assert (
            sheet["warmup_minutes"]
            + sum(o["teach_minutes"] + o["check_minutes"] for o in sheet["objectives"])
            + sheet["closing_minutes"]
            + next(s["minutes"] for s in sheet["stages"] if s["name"] == "objectives")
            == 45
        )
        assert len(sheet["checks"]) == 15

        response = teacher_client.get(f"{base}/word")
        assert response.status_code == 200
        assert (
            response["Content-Disposition"]
            == f'attachment; filename="prep-{GRADE10_SLUG}-{period["lesson"]}-k{period["k"]}.docx"'
        )
        text = document_text(response.content)
        assert not TOKEN.findall(text), base
        assert f"الأسبوع {period['week']}، الحصة {period['k']} من {period['n']}" in text
        # صفّا الهدف لكل هدف: جدول التحضير يزيد صفّين لكل هدف بعد الأول
        rows = len(Document(BytesIO(response.content)).tables[0].rows)
        assert rows == 17 + 2 * (len(sheet["objectives"]) - 1)
        for objective in sheet["objectives"]:
            assert objective["text"] in text


@pytest.mark.django_db
def test_unapproved_objectives_are_marked_pending_in_page_and_word(teacher_client):
    base = f"{API}/{GRADE10_SLUG}/2.1/1"  # الوحدة 2 لم تُعتمد نصوصها بعد
    sheet = teacher_client.get(base).json()
    assert sheet["pending"] is True
    first = sheet["objectives"][0]
    assert first["pending"] and PENDING_MARK in first["text"] and f"مثال {first['example']}" in first["text"]
    assert {c["code"]: c["status"] for c in sheet["checks"]}["T2c"] == "pending"
    document = Document(BytesIO(teacher_client.get(f"{base}/word").content))
    assert PENDING_MARK in document.tables[0].rows[TEACH_ROW].cells[0].text


@pytest.mark.django_db
def test_approved_unit_objectives_and_outcomes_reach_page_and_word(teacher_client):
    unit = unit_prep(GRADE10_SLUG, 1)
    assert unit is not None and unit.status == "approved"
    base = f"{API}/{GRADE10_SLUG}/1.2/1"
    sheet = teacher_client.get(base).json()
    assert sheet["pending"] is False
    expected = [
        " ".join((o.behavior, o.condition, o.criterion)) for o in unit.objectives("1.2").values()
    ][: len(sheet["objectives"])]
    assert [o["text"] for o in sheet["objectives"]] == expected
    assert {c["code"]: c["status"] for c in sheet["checks"]}["T2c"] == "pass"
    texts = approved_standards(GRADE10_SLUG)
    assert sheet["outcomes"].startswith("10.3.2: ") and texts["10.3.3"].rstrip(".") in sheet["outcomes"]
    text = document_text(teacher_client.get(f"{base}/word").content)
    assert expected[0] in text and sheet["outcomes"] in text and PENDING_MARK not in text


@pytest.mark.django_db
def test_word_carries_teacher_year_and_is_audited(teacher_client):
    response = teacher_client.get(f"{API}/{GRADE10_SLUG}/1.1/1/word")
    text = document_text(response.content)
    assert "2026" in text and "2027" in text
    assert "الصف 10" in text and "الوحدة 1" in text
    assert response["Cache-Control"] == "private, no-store"
    assert AuditLog.objects.filter(action="preps.word", target=f"{GRADE10_SLUG}/1.1/1").exists()


@pytest.mark.django_db
def test_last_period_is_review_and_lesson_quiz(teacher_client):
    periods = teacher_client.get(f"{API}/{GRADE10_SLUG}").json()
    last = next(p for p in periods if p["k"] == p["n"])
    sheet = teacher_client.get(f"{API}/{GRADE10_SLUG}/{last['lesson']}/{last['k']}").json()
    assert [o["example"] for o in sheet["objectives"]] == [None]
    assert "اختبار الدرس" in sheet["objectives"][0]["check_assessment"]
