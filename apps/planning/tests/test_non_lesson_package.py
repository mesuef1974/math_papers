"""باقة حصص غير الدروس (المرحلة 4): أوراقها المربوطة ملفاتٍ بمفاتيحها، ببذرة ثابتة، لكل حصة غير درس في الخطة."""

import io
import zipfile

import pytest
from django.core.cache import cache

from apps.curriculum.courses import GRADE10_SLUG
from apps.papers import pdf
from apps.papers.api import PrintPayload
from apps.planning import non_lesson_package, package_build, selectors

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("loaded_courses", "local_store")]


@pytest.fixture(autouse=True)
def rendered(monkeypatch):
    cache.clear()
    calls: list[dict] = []

    def render(payload):
        calls.append(payload)
        return b"%PDF-1.7 sheet"

    monkeypatch.setattr(pdf, "render_payload", render)
    yield calls
    cache.clear()


def test_every_non_lesson_period_has_printable_deterministic_papers():
    items = selectors.non_lesson_preps(GRADE10_SLUG)
    assert items
    for item in items:
        payloads, missing = non_lesson_package.print_payloads(item.prep, {})
        assert not missing, (item.prep.slug, missing)
        assert len(payloads) == 2 * len(item.prep.papers)
        assert [p["show_key"] for _, p in payloads] == [False, True] * len(item.prep.papers)
        assert len({name for name, _ in payloads}) == len(payloads)
        for _, payload in payloads:
            PrintPayload.model_validate({**payload, "profile": {"subject": "الرياضيات", "exam_minutes": 60}})
        assert non_lesson_package.print_payloads(item.prep, {})[0] == payloads


@pytest.mark.parametrize("kind", ["quiz", "review", "orientation"])
def test_teacher_downloads_a_non_lesson_package(teacher_client, rendered, kind):
    prep = next(p.prep for p in selectors.non_lesson_preps(GRADE10_SLUG) if p.prep.kind == kind)
    url = f"/api/v1/preps/{GRADE10_SLUG}/{prep.slug}/{prep.k}/package"
    before = teacher_client.get(url).json()
    assert before["status"] == "idle" and before["sheets"] == [p.label for p in prep.papers]

    assert teacher_client.post(url).json()["status"] == "ready"
    response = teacher_client.get(f"{url}/download")
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert package_build.INDEX_NAME in names and any(n.endswith(".docx") for n in names)
    assert sum(n.endswith(".pdf") for n in names) == len(rendered) == 2 * len(prep.papers)
    assert not any(n.endswith(".pptx") for n in names)
