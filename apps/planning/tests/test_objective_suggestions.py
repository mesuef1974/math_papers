"""جانب المالك من مراجعة الأهداف (المرحلة 3 من docs/teacher_objective_review_plan.md).

لوحة الاقتراحات تعرض المعتمد والمقترح متجاورين وتقرّر عبر الخدمة وحدها؛ وأمر التطبيق يكتب المقبول وحده في ملف
الوحدة (الشرط والمعيار)، ويرفض ما يكسر المخطط، ويتخطّى ما تغيّر معتمده بعده، وتشغيله مرتين لا يغيّر شيئًا.
"""

import json
import shutil
from datetime import date
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.core.models import AuditLog
from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import Lesson
from apps.knowledge.domain.contract import COURSES_DIR
from apps.knowledge.domain.unit_prep import unit_prep
from apps.planning import services
from apps.planning.domain.calendar_engine import PlanningError
from apps.planning.domain.objective_text import digest
from apps.planning.models import ObjectiveSuggestion

pytestmark = [pytest.mark.usefixtures("loaded_courses"), pytest.mark.django_db]

CONDITION = "باستعمال جدول قيم لدالة تربيعية معطاة"
CRITERION = "بدقة تامة في ثلاث محاولات من أربع"
TODAY = date(2026, 11, 20)
PASSWORD = "Rasm-Bayani-2026"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _fresh_unit_cache():
    unit_prep.cache_clear()
    yield
    unit_prep.cache_clear()


@pytest.fixture
def unit_root(tmp_path):
    """نسخة من ملف الوحدة الأولى ووصف المعايير في مجلد مؤقت: الأمر يكتب فيها لا في المستودع."""
    target = tmp_path / GRADE10_SLUG
    (target / "prep").mkdir(parents=True)
    shutil.copy(COURSES_DIR / GRADE10_SLUG / "prep" / "unit-1.json", target / "prep" / "unit-1.json")
    shutil.copy(COURSES_DIR / GRADE10_SLUG / "standards.json", target / "standards.json")
    return tmp_path


def unit_file(root):
    return root / GRADE10_SLUG / "prep" / "unit-1.json"


def objective(root, lesson="1.1", example=1) -> dict:
    raw = json.loads(unit_file(root).read_text(encoding="utf-8"))
    entry = next(e for e in raw["lessons"] if e["lesson"] == lesson)
    return next(o for o in entry["objectives"] if o["example"] == example)


def teacher(name="teacher"):
    return get_user_model().objects.get_or_create(username=name)[0]


def suggest(
    root=COURSES_DIR, *, example=1, decision=ObjectiveSuggestion.ACCEPTED, base=None, owner=None, **text
):
    shared = objective(root, example=example)
    return ObjectiveSuggestion.objects.create(
        owner=owner or teacher(),
        lesson=Lesson.objects.get(course__slug=GRADE10_SLUG, code="1.1"),
        example=example,
        condition=text.get("condition", CONDITION),
        criterion=text.get("criterion", CRITERION),
        base_digest=base or digest((shared["behavior"], shared["condition"], shared["criterion"])),
        decision=decision,
    )


# ───── أمر التطبيق ─────


def test_apply_objective_writes_only_accepted_and_is_idempotent(unit_root):
    before = objective(unit_root, example=2)
    behavior = objective(unit_root)["behavior"]
    accepted = suggest(unit_root)
    suggest(unit_root, example=2, decision=ObjectiveSuggestion.REJECTED, owner=teacher("t2"))
    suggest(unit_root, example=2, decision=ObjectiveSuggestion.PENDING, owner=teacher("t3"))

    result = services.apply_objective_suggestions(GRADE10_SLUG, 1, root=unit_root, today=TODAY)

    assert [item.suggestion for item in result.applied] == [accepted.pk] and not result.skipped
    written = objective(unit_root)
    assert (written["condition"], written["criterion"], written["behavior"]) == (
        CONDITION,
        CRITERION,
        behavior,
    )
    assert objective(unit_root, example=2) == before
    raw = json.loads(unit_file(unit_root).read_text(encoding="utf-8"))
    assert raw["approval"] == "اعتُمد من المالك — 2026-11-20"
    assert AuditLog.objects.filter(action="prep.suggestion.apply").count() == 1

    content = unit_file(unit_root).read_bytes()
    again = services.apply_objective_suggestions(GRADE10_SLUG, 1, root=unit_root, today=date(2026, 12, 1))
    assert not again.changed and unit_file(unit_root).read_bytes() == content
    assert AuditLog.objects.filter(action="prep.suggestion.apply").count() == 1


def test_apply_objective_skips_suggestion_whose_shared_text_changed(unit_root):
    content = unit_file(unit_root).read_bytes()
    stale = suggest(unit_root, base="0" * 16)
    result = services.apply_objective_suggestions(GRADE10_SLUG, 1, root=unit_root, today=TODAY)
    assert not result.changed and str(stale.pk) in result.skipped[0]
    assert unit_file(unit_root).read_bytes() == content


def test_apply_objective_rejects_text_that_breaks_the_schema(unit_root):
    content = unit_file(unit_root).read_bytes()
    suggest(unit_root, condition="أ")
    with pytest.raises(PlanningError):
        services.apply_objective_suggestions(GRADE10_SLUG, 1, root=unit_root, today=TODAY)
    assert unit_file(unit_root).read_bytes() == content


def test_apply_objective_refuses_a_draft_unit(unit_root):
    raw = json.loads(unit_file(unit_root).read_text(encoding="utf-8"))
    raw.update(status="draft", approval=None)
    unit_file(unit_root).write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    suggest(unit_root)
    with pytest.raises(PlanningError):
        services.apply_objective_suggestions(GRADE10_SLUG, 1, root=unit_root, today=TODAY)


def test_apply_objective_command_dry_run_does_not_write():
    content = unit_file(COURSES_DIR).read_bytes()
    out = StringIO()
    call_command("apply_objective_suggestions", GRADE10_SLUG, "--unit", "1", "--dry-run", stdout=out)
    assert "لا تغيير" in out.getvalue()
    suggest()
    out = StringIO()
    call_command("apply_objective_suggestions", GRADE10_SLUG, "--unit", "1", "--dry-run", stdout=out)
    assert "سيُكتب 1" in out.getvalue() and CONDITION in out.getvalue()
    assert unit_file(COURSES_DIR).read_bytes() == content
    assert not AuditLog.objects.filter(action="prep.suggestion.apply").exists()


# ───── لوحة الاقتراحات ─────

ADMIN = "/admin/planning/objectivesuggestion/"


@pytest.fixture
def owner_client(client):
    client.force_login(get_user_model().objects.create_superuser("owner", password=PASSWORD))
    return client


def test_admin_suggestion_list_shows_shared_and_suggested_side_by_side(owner_client):
    row = suggest(decision=ObjectiveSuggestion.PENDING)
    shared = objective(COURSES_DIR)
    listing = owner_client.get(ADMIN)
    assert listing.status_code == 200 and "قيد المراجعة" in listing.content.decode()
    page = owner_client.get(f"{ADMIN}{row.pk}/change/").content.decode()
    assert shared["condition"] in page and CONDITION in page and "المعتمد الحالي" in page
    assert 'name="verdict"' in page


def test_admin_suggestion_decides_through_the_service_with_a_note(owner_client):
    row = suggest(decision=ObjectiveSuggestion.PENDING)
    response = owner_client.post(
        f"{ADMIN}{row.pk}/change/", {"verdict": "rejected", "decision_note": "النص الأصلي أدق"}
    )
    assert response.status_code == 302, response.content
    row.refresh_from_db()
    assert row.decision == ObjectiveSuggestion.REJECTED and row.decision_note == "النص الأصلي أدق"
    assert row.decided_by.username == "owner"
    assert AuditLog.objects.filter(action="prep.suggestion.decide").count() == 1
    page = owner_client.get(f"{ADMIN}{row.pk}/change/").content.decode()
    assert 'name="verdict"' not in page


def test_admin_suggestion_note_without_verdict_is_refused(owner_client):
    row = suggest(decision=ObjectiveSuggestion.PENDING)
    response = owner_client.post(f"{ADMIN}{row.pk}/change/", {"verdict": "", "decision_note": "ملاحظة"})
    assert response.status_code == 200
    row.refresh_from_db()
    assert row.decision == ObjectiveSuggestion.PENDING and row.decision_note == ""


def test_admin_suggestion_actions_decide_pending_only(owner_client):
    pending = suggest(decision=ObjectiveSuggestion.PENDING)
    decided = suggest(decision=ObjectiveSuggestion.REJECTED, owner=teacher("t2"))
    response = owner_client.post(
        ADMIN, {"action": "accept_selected", "_selected_action": [pending.pk, decided.pk]}, follow=True
    )
    assert response.status_code == 200
    pending.refresh_from_db()
    decided.refresh_from_db()
    assert (
        pending.decision == ObjectiveSuggestion.ACCEPTED and decided.decision == ObjectiveSuggestion.REJECTED
    )
    assert "تُخطّي 1" in response.content.decode()


def test_admin_suggestion_requires_the_decide_permission(client):
    staff = get_user_model().objects.create_user("staff", password=PASSWORD, is_staff=True)
    client.force_login(staff)
    assert client.get(ADMIN).status_code == 403
    client.logout()
    assert client.get(ADMIN).status_code == 302


def test_accepted_suggestion_is_shown_applied_after_the_file_matches(owner_client):
    shared = objective(COURSES_DIR)
    suggest(condition=shared["condition"], criterion=shared["criterion"])
    assert "مُطبَّق" in owner_client.get(ADMIN).content.decode()
