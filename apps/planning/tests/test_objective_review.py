"""مراجعة المعلم لأهداف حصته (المرحلة 1 من docs/teacher_objective_review_plan.md).

نسخة المعلم الشخصية للشرط والمعيار تظهر له وحده في الصفحة وWord، والسلوك والعمق والمعايير T1 إلى T13 لا تتغير؛
الوحدة غير المعتمدة لا تُعدَّل؛ الاقتراح لقطة يقرّرها المالك وحده مرة واحدة؛ وكل كتابة سطر في سجل التدقيق.
"""

import pytest
from django.contrib.auth import get_user_model

from apps.core.models import AuditLog
from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import Lesson
from apps.papers.access import ensure_teacher
from apps.planning import services
from apps.planning.domain.objective_text import ObjectiveTextError, clean_note, clean_part, digest
from apps.planning.models import ObjectiveOverride, ObjectiveSuggestion, PrepReview

from .test_prep_api import document_text

API = f"/api/v1/preps/{GRADE10_SLUG}"
PERIOD = f"{API}/1.1/1"
CONDITION = "باستعمال جدول قيم لدالة أسية معطاة"
CRITERION = "بدقة تامة في ثلاث محاولات من أربع"

pytestmark = [pytest.mark.usefixtures("loaded_courses"), pytest.mark.django_db]


def objectives(client, path=PERIOD):
    response = client.get(path)
    assert response.status_code == 200, response.content
    return response.json()


def first_example(client) -> dict:
    return next(o for o in objectives(client)["objectives"] if o["example"] is not None)


def put(client, example, condition=CONDITION, criterion=CRITERION, **extra):
    return client.put(
        f"{PERIOD}/objectives/{example}",
        {"condition": condition, "criterion": criterion, **extra},
        content_type="application/json",
    )


def locked_period(client, unit: int) -> str:
    """أول حصة في الوحدة unit (مسودة بالتجهيز draft_unit)."""
    periods = client.get(API).json()
    period = next(p for p in periods if p["unit"] == unit)
    return f"{API}/{period['lesson']}/{period['k']}"


# ───── التنظيف والبصمة ─────


def test_clean_part_collapses_spaces_and_rejects_tags_controls_and_lengths():
    assert clean_part("  بدقة\n تامة\tجدًا  ", "المعيار") == "بدقة تامة جدًا"
    for bad in ("<b>بدقة</b>", "س < 3", "بدقة\x00تامة", "ب", "م" * 241):
        with pytest.raises(ObjectiveTextError):
            clean_part(bad, "المعيار")
    assert clean_note(None) == clean_note("   ") == ""
    assert digest(["أ", "ب"]) != digest(["أب", ""]) and len(digest(["أ"])) == 16


# ───── الدخول والصلاحية ─────


WRITES = (
    ("put", f"{PERIOD}/objectives/1"),
    ("delete", f"{PERIOD}/objectives/1"),
    ("post", f"{PERIOD}/review"),
)


@pytest.mark.parametrize(("method", "path"), WRITES)
def test_writes_require_a_session(client, method, path):
    assert getattr(client, method)(path, content_type="application/json").status_code == 401


@pytest.mark.parametrize(("method", "path"), WRITES)
def test_writes_require_the_teacher_permission(outsider_client, method, path):
    assert getattr(outsider_client, method)(path, content_type="application/json").status_code == 403


# ───── القراءة ─────


def test_approved_unit_objectives_are_editable_with_shared_text_and_no_copy(teacher_client):
    sheet = objectives(teacher_client)
    assert sheet["review"] is None
    for row in (o for o in sheet["objectives"] if o["example"] is not None):
        assert row["editable"] and row["mine"] is None and row["suggestion"] is None and not row["stale"]
        shared = row["shared"]
        assert row["text"] == " ".join((shared["behavior"], shared["condition"], shared["criterion"]))


def test_unapproved_unit_is_locked(teacher_client, draft_unit):
    path = locked_period(teacher_client, draft_unit)
    rows = [o for o in objectives(teacher_client, path)["objectives"] if o["example"] is not None]
    assert rows and all(not o["editable"] and o["shared"] is None for o in rows)
    response = teacher_client.put(
        f"{path}/objectives/{rows[0]['example']}",
        {"condition": CONDITION, "criterion": CRITERION},
        content_type="application/json",
    )
    assert response.status_code == 409
    assert not ObjectiveOverride.objects.exists()


def test_unknown_example_or_period_is_404(teacher_client):
    assert put(teacher_client, 39).status_code == 404
    assert (
        teacher_client.put(
            f"{API}/1.1/99/objectives/1",
            {"condition": CONDITION, "criterion": CRITERION},
            content_type="application/json",
        ).status_code
        == 404
    )


# ───── الحفظ والاسترجاع ─────


def test_save_changes_only_condition_and_criterion_and_reaches_word(teacher_client):
    before = objectives(teacher_client)
    row = first_example(teacher_client)
    response = put(teacher_client, row["example"])
    assert response.status_code == 200, response.content
    sheet = response.json()
    mine = next(o for o in sheet["objectives"] if o["example"] == row["example"])
    assert mine["mine"] == {"condition": CONDITION, "criterion": CRITERION}
    assert mine["shared"] == row["shared"] and not mine["stale"]
    assert mine["text"] == " ".join((row["shared"]["behavior"], CONDITION, CRITERION))
    assert sheet["checks"] == before["checks"]  # T1 إلى T13 لا تتغير بنسخة المعلم
    word = teacher_client.get(f"{PERIOD}/word")
    assert word.status_code == 200 and CRITERION in document_text(word.content)
    log = AuditLog.objects.get(action="prep.objective.save")
    assert log.target == f"{GRADE10_SLUG}/1.1#{row['example']}"
    assert log.payload["after"] == [CONDITION, CRITERION]


def test_save_is_idempotent(teacher_client):
    example = first_example(teacher_client)["example"]
    assert put(teacher_client, example).status_code == 200
    assert put(teacher_client, example).status_code == 200
    assert ObjectiveOverride.objects.count() == 1
    assert AuditLog.objects.filter(action="prep.objective.save").count() == 1


def test_text_equal_to_shared_removes_the_copy(teacher_client):
    row = first_example(teacher_client)
    put(teacher_client, row["example"])
    response = put(teacher_client, row["example"], row["shared"]["condition"], row["shared"]["criterion"])
    assert response.status_code == 200
    assert not ObjectiveOverride.objects.exists()


@pytest.mark.parametrize("criterion", ["ب", "<script>x</script>", "م" * 241])
def test_invalid_text_is_422(teacher_client, criterion):
    assert (
        put(teacher_client, first_example(teacher_client)["example"], criterion=criterion).status_code == 422
    )
    assert not ObjectiveOverride.objects.exists()


def test_reset_restores_shared_and_is_idempotent(teacher_client):
    row = first_example(teacher_client)
    put(teacher_client, row["example"])
    path = f"{PERIOD}/objectives/{row['example']}"
    first = teacher_client.delete(path)
    assert first.status_code == 200
    restored = next(o for o in first.json()["objectives"] if o["example"] == row["example"])
    assert restored["mine"] is None and restored["text"] == row["text"]
    assert teacher_client.delete(path).status_code == 200
    assert AuditLog.objects.filter(action="prep.objective.reset").count() == 1


def test_copy_is_stale_when_shared_text_changed_after_edit(teacher_client):
    example = first_example(teacher_client)["example"]
    put(teacher_client, example)
    ObjectiveOverride.objects.update(base_digest="0" * 16)
    row = next(o for o in objectives(teacher_client)["objectives"] if o["example"] == example)
    assert row["stale"] and row["mine"] is not None
    put(teacher_client, example, criterion=CRITERION + " دون مساعدة")  # الحفظ من جديد يحدّث البصمة
    row = next(o for o in objectives(teacher_client)["objectives"] if o["example"] == example)
    assert not row["stale"]


def test_teachers_do_not_see_each_others_copies(teacher_client, client):
    example = first_example(teacher_client)["example"]
    put(teacher_client, example)
    other, _ = ensure_teacher("teacher2", "Rasm-Bayani-2026")  # pragma: allowlist secret
    client.force_login(other)
    row = next(o for o in objectives(client)["objectives"] if o["example"] == example)
    assert row["mine"] is None and CRITERION not in row["text"]


# ───── الاقتراح وقرار المالك ─────


def test_suggestion_snapshot_replaces_pending_one(teacher_client):
    example = first_example(teacher_client)["example"]
    put(teacher_client, example, suggest=True, note="أوضح للطلاب")
    put(teacher_client, example, suggest=True, note="أوضح للطلاب")  # التكرار لا ينشئ لقطة جديدة
    assert ObjectiveSuggestion.objects.count() == 1
    put(teacher_client, example, criterion=CRITERION + " دون مساعدة", suggest=True)
    pending = ObjectiveSuggestion.objects.filter(decision=ObjectiveSuggestion.PENDING)
    assert pending.count() == 1 and pending.get().criterion.endswith("دون مساعدة")
    row = next(o for o in objectives(teacher_client)["objectives"] if o["example"] == example)
    assert row["suggestion"]["status"] == "pending"
    assert AuditLog.objects.filter(action="prep.objective.suggest").count() == 2


def test_suggestion_equal_to_shared_is_rejected(teacher_client):
    row = first_example(teacher_client)
    response = put(
        teacher_client, row["example"], row["shared"]["condition"], row["shared"]["criterion"], suggest=True
    )
    assert response.status_code == 422
    assert not ObjectiveSuggestion.objects.exists()


def test_only_the_owner_decides_once(teacher_client):
    example = first_example(teacher_client)["example"]
    put(teacher_client, example, suggest=True)
    suggestion = ObjectiveSuggestion.objects.get()
    teacher = suggestion.owner
    with pytest.raises(PermissionError):
        services.decide_suggestion(teacher, suggestion.pk, ObjectiveSuggestion.ACCEPTED)
    password = "Rasm-Bayani-2026"  # pragma: allowlist secret
    owner = get_user_model().objects.create_superuser("owner", password=password)
    with pytest.raises(services.PlanningError):
        services.decide_suggestion(owner, suggestion.pk, "maybe")
    decided = services.decide_suggestion(
        owner, suggestion.pk, ObjectiveSuggestion.REJECTED, "النص الأصلي أدق"
    )
    assert decided.decision == ObjectiveSuggestion.REJECTED and decided.decided_by == owner
    with pytest.raises(services.SuggestionDecidedError):
        services.decide_suggestion(owner, suggestion.pk, ObjectiveSuggestion.ACCEPTED)
    assert AuditLog.objects.filter(action="prep.suggestion.decide").count() == 1
    row = next(o for o in objectives(teacher_client)["objectives"] if o["example"] == example)
    assert row["suggestion"]["status"] == "rejected" and row["suggestion"]["note"] == "النص الأصلي أدق"


def test_accepted_suggestion_matching_shared_text_is_applied(teacher_client):
    row = first_example(teacher_client)
    teacher = get_user_model().objects.get(username="teacher")
    ObjectiveSuggestion.objects.create(
        owner=teacher,
        lesson=Lesson.objects.get(course__slug=GRADE10_SLUG, code="1.1"),
        example=row["example"],
        condition=row["shared"]["condition"],
        criterion=row["shared"]["criterion"],
        base_digest="0" * 16,
        decision=ObjectiveSuggestion.ACCEPTED,
    )
    current = next(o for o in objectives(teacher_client)["objectives"] if o["example"] == row["example"])
    assert current["suggestion"]["status"] == "applied"


# ───── علامة المراجعة ─────


def test_review_mark_turns_stale_when_texts_change(teacher_client):
    response = teacher_client.post(f"{PERIOD}/review")
    assert response.status_code == 200
    review = response.json()["review"]
    assert review["reviewed_at"] and not review["stale"]
    assert teacher_client.post(f"{PERIOD}/review").status_code == 200
    assert PrepReview.objects.count() == 1
    put(teacher_client, first_example(teacher_client)["example"])
    assert objectives(teacher_client)["review"]["stale"]
    assert AuditLog.objects.filter(action="prep.review").count() == 2
