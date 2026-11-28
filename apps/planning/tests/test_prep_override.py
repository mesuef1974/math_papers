"""تعديل المعلم لتحضير حصص درس (المرحلة 6 من docs/lesson_prep_plan.md).

المخطط مقيَّد ويحفظ قواعد التوزيع والمكتبة؛ التعديل يدخل الاشتقاق نفسه ثم تُعاد المعايير، ولا يُحفظ ما يُفشل معيارًا حاجبًا؛
وهو للمعلم وحده؛ والتعديل المحفوظ يعلّم آخر عرض طلبه المعلم للحصة قديمًا.
"""

import pytest

from apps.core.models import AuditLog
from apps.curriculum.courses import GRADE10_SLUG
from apps.planning import selectors, services
from apps.planning.domain.prep import TeacherEdit, stage_options
from apps.planning.domain.prep_override import OverrideError, dump_override, parse_override
from apps.planning.domain.strategies import load_library
from apps.planning.models import DeckBuild, PeriodPrepOverride

from .test_deck_jobs import _publish

API = f"/api/v1/preps/{GRADE10_SLUG}"
LESSON = "1.1"
DEFAULT = [[1, 2, 3], [4, 5], []]  # توزيع allocate لأمثلة 1.1 على حصصه الثلاث
MOVED = [[1, 2], [3, 4, 5], []]

pytestmark = [pytest.mark.usefixtures("loaded_courses"), pytest.mark.django_db]


def sheet(client, k=1, lesson=LESSON):
    response = client.get(f"{API}/{lesson}/{k}")
    assert response.status_code == 200, response.content
    return response.json()


def put(client, data, k=1, lesson=LESSON):
    return client.put(f"{API}/{lesson}/{k}/override", data, content_type="application/json")


def examples_of(client, k):
    return [o["example"] for o in sheet(client, k)["objectives"] if o["example"] is not None]


def alternative(stage: dict) -> str:
    return next(o["slug"] for o in stage["options"] if o["slug"] != stage["current"])


# ───── المخطط ─────


LIBRARY = load_library()


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"extra": 1},
        {"allocation": [[1, 2, 3], [4, 5]]},  # عدد الحصص
        {"allocation": [[1, 2], [3, 4], [5]]},  # الأخيرة بمثال
        {"allocation": [[2, 1, 3], [4, 5], []]},  # الترتيب
        {"allocation": [[1, 2, 3, 4], [5], []]},  # أكثر من ثلاثة
        {"allocation": [[1, 2, 3], [4], []]},  # مثال مفقود
        {"allocation": [[1, 2, True], [4, 5], []]},
        {"periods": {"9": {}}},
        {"periods": {"1": {"other": 1}}},
        {"periods": {"1": {"strategies": {"objectives": "x"}}}},
        {"periods": {"1": {"strategies": {"guided": "no-such-strategy"}}}},
        {"periods": {"1": {"removed": [0]}}},
    ],
)
def test_schema_rejects_what_breaks_the_allocation_or_library_rules(data):
    with pytest.raises(OverrideError):
        parse_override(data, examples=[1, 2, 3, 4, 5], n=3, library=LIBRARY)


def test_canonical_form_drops_what_equals_the_derived_prep():
    slug = stage_options(LIBRARY, "guided")[0].slug
    parsed = parse_override(
        {
            "allocation": DEFAULT,
            "periods": {"2": {"removed": [9, 7]}, "1": {}, "3": {"strategies": {"guided": slug}}},
        },
        examples=[1, 2, 3, 4, 5],
        n=3,
        library=LIBRARY,
    )
    assert dump_override(parsed, DEFAULT) == {
        "periods": {"2": {"removed": [7, 9]}, "3": {"strategies": {"guided": slug}}}
    }
    assert dump_override(parse_override({}, examples=[1, 2, 3, 4, 5], n=3, library=LIBRARY), DEFAULT) == {}


# ───── الاشتقاق ─────


def test_edit_enters_the_derivation_and_marks_its_sources():
    shared = selectors.period_item(GRADE10_SLUG, LESSON, 1)
    direct = next(s for s in shared.prep.stages if s.name == "direct")
    slug = next(o.slug for o in stage_options(LIBRARY, "direct") if o.slug != direct.strategy)
    dropped = shared.prep.classwork[0].exercises[0]
    items = selectors.lesson_preps(
        GRADE10_SLUG, {LESSON: {"periods": {"1": {"strategies": {"direct": slug}, "removed": [dropped]}}}}
    )
    prep = next(i for i in items if i.prep.lesson == LESSON and i.prep.k == 1).prep
    assert next(s for s in prep.stages if s.name == "direct").strategy == slug
    assert sum(s.minutes for s in prep.stages) == prep.minutes
    used = {x for c in prep.classwork for x in c.exercises} | {*prep.basic, *prep.advanced, *prep.homework}
    assert dropped not in used
    assert prep.sources["stages"] == prep.sources["practice"] == "teacher"
    assert prep.sources["allocation"] == "plan"
    assert TeacherEdit().removed == frozenset()


def test_stored_edit_that_no_longer_fits_the_lesson_is_ignored_and_flagged():
    items = selectors.lesson_preps(GRADE10_SLUG, {LESSON: {"allocation": [[1], [2], []]}})
    mine = [i for i in items if i.prep.lesson == LESSON]
    assert {i.override for i in mine} == {"invalid"}
    assert [list(i.allocation[0]) for i in mine[:1]] == [DEFAULT[0]]
    with pytest.raises(OverrideError):
        selectors.lesson_preps(GRADE10_SLUG, {LESSON: {"allocation": [[1], [2], []]}}, strict=True)


# ───── الحفظ والصلاحية ─────


WRITES = (("put", f"{API}/{LESSON}/1/override"), ("delete", f"{API}/{LESSON}/1/override"))


@pytest.mark.parametrize(("method", "path"), WRITES)
def test_writes_require_a_session(client, method, path):
    assert getattr(client, method)(path, {}, content_type="application/json").status_code == 401


@pytest.mark.parametrize(("method", "path"), WRITES)
def test_writes_require_the_teacher_permission(outsider_client, method, path):
    assert getattr(outsider_client, method)(path, {}, content_type="application/json").status_code == 403


def test_sheet_offers_the_edit_with_the_derived_allocation(teacher_client):
    edit = sheet(teacher_client)["edit"]
    assert edit["state"] == "none" and edit["allocation"] == edit["default_allocation"] == DEFAULT
    assert edit["removed"] == [] and edit["exercises"]
    assert edit["exercise_pages"] and set(map(int, edit["exercise_pages"])) <= set(edit["exercises"])
    assert all(s["chosen"] is None and len(s["options"]) >= 1 for s in edit["stages"])


def test_moving_an_example_changes_both_periods_for_this_teacher_only(teacher_client, django_user_model):
    response = put(teacher_client, {"allocation": MOVED})
    assert response.status_code == 200, response.content
    assert response.json()["edit"]["state"] == "active"
    assert examples_of(teacher_client, 1) == [1, 2] and examples_of(teacher_client, 2) == [3, 4, 5]
    periods = teacher_client.get(API).json()
    assert {p["k"] for p in periods if p["lesson"] == LESSON and p["customized"]} == {1, 2, 3}
    # التحضير المشترك ومعلم آخر لا يتغيران
    assert [e.n for e in selectors.period_item(GRADE10_SLUG, LESSON, 1).prep.examples] == DEFAULT[0]
    other = django_user_model.objects.create_user("other-teacher")
    assert [e.n for e in selectors.period_item(GRADE10_SLUG, LESSON, 1, other).prep.examples] == DEFAULT[0]
    log = AuditLog.objects.filter(action="prep.override.save").get()
    assert log.payload == {"before": {}, "after": {"allocation": MOVED}}


def test_saving_is_idempotent_and_the_no_op_edit_deletes_the_record(teacher_client):
    assert put(teacher_client, {"allocation": MOVED}).status_code == 200
    assert put(teacher_client, {"allocation": MOVED}).status_code == 200
    assert AuditLog.objects.filter(action="prep.override.save").count() == 1
    assert put(teacher_client, {"allocation": DEFAULT}).status_code == 200
    assert not PeriodPrepOverride.objects.exists()
    assert AuditLog.objects.filter(action="prep.override.reset").count() == 1


def test_reset_restores_the_shared_prep(teacher_client):
    stage = sheet(teacher_client, 2)["edit"]["stages"][0]
    put(teacher_client, {"strategies": {stage["name"]: alternative(stage)}}, k=2)
    assert sheet(teacher_client, 2)["edit"]["stages"][0]["chosen"] == alternative(stage)
    response = teacher_client.delete(f"{API}/{LESSON}/2/override")
    assert response.status_code == 200 and response.json()["edit"]["state"] == "none"
    assert not PeriodPrepOverride.objects.exists()


@pytest.mark.parametrize(
    "data",
    [
        {"allocation": [[1], [2], []]},
        {"removed": [999]},  # ليس من تمارين الحصة
        {"strategies": {"guided": "no-such-strategy"}},
    ],
)
def test_invalid_edits_are_rejected_without_writing(teacher_client, data):
    response = put(teacher_client, data)
    assert response.status_code == 422, response.content
    assert response.json()["detail"]
    assert not PeriodPrepOverride.objects.exists()
    assert not AuditLog.objects.filter(action__startswith="prep.override").exists()


def test_edit_that_fails_a_blocking_check_is_not_saved(teacher_client):
    """حذف تمارين الصف كلها لمثال يتركه بلا تدريب صفي (T4)، فيُرفض التعديل."""
    prep = selectors.period_item(GRADE10_SLUG, LESSON, 1).prep
    example = next(e for e in prep.examples if not e.conceptual and e.rows)
    exercises = sorted({x for _, ex in example.rows for x in ex})
    response = put(teacher_client, {"removed": exercises})
    assert response.status_code == 422, response.content
    assert "معيارًا حاجبًا" in response.json()["detail"]
    assert not PeriodPrepOverride.objects.exists()


def test_service_raises_for_an_unknown_lesson(django_user_model):
    owner = django_user_model.objects.create_user("t")
    with pytest.raises(selectors.PrepNotFoundError):
        services.save_prep_override(owner, GRADE10_SLUG, "9.9", {})


# ───── العرض القديم ─────


def test_saved_edit_marks_the_last_requested_deck_stale(teacher_client, local_store):
    item = selectors.period_item(GRADE10_SLUG, LESSON, 1)
    _publish(LESSON, item.prep.examples)
    response = teacher_client.post(
        "/api/v1/decks/", {"course": GRADE10_SLUG, "lesson": LESSON, "k": 1}, content_type="application/json"
    )
    assert response.status_code == 200, response.content
    first = DeckBuild.objects.get()
    assert first.k == 1

    def row():
        periods = teacher_client.get(f"/api/v1/decks/periods?course={GRADE10_SLUG}").json()
        return next(p for p in periods if p["lesson"] == LESSON and p["k"] == 1)

    assert row()["stale"] is False
    stage = sheet(teacher_client)["edit"]["stages"][0]
    assert put(teacher_client, {"strategies": {stage["name"]: alternative(stage)}}).status_code == 200
    assert row()["stale"] is True and row()["customized"] is True
    # العرض الجديد يُبنى من تحضير المعلم بمفتاح جديد، فيعود غير قديم
    teacher_client.post(
        "/api/v1/decks/", {"course": GRADE10_SLUG, "lesson": LESSON, "k": 1}, content_type="application/json"
    )
    assert DeckBuild.objects.get().key != first.key
    assert row()["stale"] is False


def test_period_edits_merge_and_keep_other_periods(teacher_client):
    first, second = (
        sheet(teacher_client, 1)["edit"]["stages"][0],
        sheet(teacher_client, 2)["edit"]["stages"][0],
    )
    put(teacher_client, {"strategies": {first["name"]: alternative(first)}}, k=1)
    put(teacher_client, {"strategies": {second["name"]: alternative(second)}}, k=2)
    assert sheet(teacher_client, 1)["edit"]["stages"][0]["chosen"] == alternative(first)
    put(teacher_client, {"strategies": {}}, k=1)
    assert sheet(teacher_client, 1)["edit"]["stages"][0]["chosen"] is None
    assert sheet(teacher_client, 2)["edit"]["stages"][0]["chosen"] == alternative(second)
