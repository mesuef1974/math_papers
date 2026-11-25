"""تشخيص الخطأ: نتيجة الطالب لكل بند (قرار المالك 2026-11-25).

الإدخال دفعة واحدة idempotent، ونوع الخطأ من بنك البنود لا من العميل، والمعلم لا يرى إلا شعبه، وسجل التدقيق بلا أسماء،
وأمر الحذف يزيل بيانات السنة المنتهية وحدها ويبقي أعداد `ClassOutcomeRecord` المجمَّعة.
"""

import json
from datetime import date, timedelta

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client

from apps.core.models import AuditLog
from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import AcademicCalendar, CalendarTerm, Course, Lesson
from apps.papers.access import ensure_teacher
from apps.papers.domain.generators import ERROR_KINDS
from apps.papers.domain.item_bank import OPTION_COUNT, exit_ticket
from apps.planning import models, selectors, services
from apps.planning.domain import item_results
from apps.planning.domain.feedback import ClassOutcome
from apps.planning.domain.item_results import Entry, ResultsError
from apps.planning.models import ClassOutcomeRecord, ItemResult, SectionStudent

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("loaded_courses")]

LESSON, EXAMPLE, SEED = "1.1", 2, 3
URL = f"/api/v1/results/{GRADE10_SLUG}/{LESSON}"
SECTION = "10/3"
FIRST, LAST = "سالم", "المري"
SECOND_FIRST, SECOND_LAST = "عبد الله", "آل ثاني"
PASSWORD = "Rasm-Bayani-2026"  # pragma: allowlist secret


@pytest.fixture
def item():
    return exit_ticket(GRADE10_SLUG, LESSON, EXAMPLE, seed=SEED)


@pytest.fixture
def wrong(item) -> int:
    """رقم خيار خاطئ في البند."""
    return next(i for i, option in enumerate(item.options) if not option.correct)


def row(enrollment_no: str, choice: int, first: str = FIRST, last: str = LAST, **extra) -> dict:
    return {
        "enrollment_no": enrollment_no,
        "first_name": first,
        "last_name": last,
        "example": EXAMPLE,
        "seed": SEED,
        "choice": choice,
        **extra,
    }


def batch(item, wrong: int) -> dict:
    return {
        "section": SECTION,
        "results": [row("1001", item.answer_index), row("1002", wrong, SECOND_FIRST, SECOND_LAST)],
    }


def post(client, payload: dict, url: str = URL):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


@pytest.fixture
def other_client(db):
    """معلم ثانٍ بصلاحية المعلم كاملة: الرفض لأن الشعبة ليست له لا لنقص صلاحية."""
    teacher, _ = ensure_teacher("teacher2", PASSWORD)
    client = Client()
    client.force_login(teacher)
    return client


def test_results_require_a_session_and_the_teacher_permission(outsider_client):
    anonymous = Client()
    assert anonymous.get(f"{URL}?section={SECTION}").status_code == 401
    assert post(anonymous, {"section": SECTION, "results": [row("1001", 0)]}).status_code == 401
    assert outsider_client.get(f"{URL}?section={SECTION}").status_code == 403
    assert post(outsider_client, {"section": SECTION, "results": [row("1001", 0)]}).status_code == 403
    assert not SectionStudent.objects.exists()


def test_batch_is_saved_with_error_kind_derived_from_the_item_bank(teacher_client, item, wrong):
    response = post(teacher_client, batch(item, wrong))
    assert response.status_code == 200, response.content
    assert response.json() == {"students": 2, "results": 2, "created": 2, "updated": 0}
    right, mistaken = ItemResult.objects.order_by("student__enrollment_no")
    assert (right.correct, right.error_kind) == (True, "")
    assert (mistaken.correct, mistaken.error_kind) == (False, item.options[wrong].kind)
    assert mistaken.error_kind in ERROR_KINDS
    assert (mistaken.lesson.course.slug, mistaken.lesson.code) == (GRADE10_SLUG, LESSON)
    student = mistaken.student
    assert (student.section, student.first_name, student.last_name) == (SECTION, SECOND_FIRST, SECOND_LAST)


def test_error_kind_from_the_client_is_ignored(teacher_client, item, wrong):
    """العميل لا يقرر الصحة ولا نوع الخطأ: ما يرسله منهما يُهمل والمحفوظ من البنك."""
    forged = row("1001", wrong, correct=True, error_kind="nearby-forged")
    assert post(teacher_client, {"section": SECTION, "results": [forged]}).status_code == 200
    result = ItemResult.objects.get()
    assert (result.correct, result.error_kind) == (False, item.options[wrong].kind)


def test_repeating_the_same_batch_adds_no_row(teacher_client, item, wrong):
    post(teacher_client, batch(item, wrong))
    stamps = dict(ItemResult.objects.values_list("pk", "updated_at"))
    again = post(teacher_client, batch(item, wrong))
    assert again.json() == {"students": 2, "results": 2, "created": 0, "updated": 0}
    assert (SectionStudent.objects.count(), ItemResult.objects.count()) == (2, 2)
    assert dict(ItemResult.objects.values_list("pk", "updated_at")) == stamps


def test_a_corrected_entry_updates_the_same_row(teacher_client, item, wrong):
    post(teacher_client, batch(item, wrong))
    fixed = {"section": SECTION, "results": [row("1002", item.answer_index, "عبدالله", SECOND_LAST)]}
    assert post(teacher_client, fixed).json() == {"students": 1, "results": 1, "created": 0, "updated": 1}
    assert (SectionStudent.objects.count(), ItemResult.objects.count()) == (2, 2)
    result = ItemResult.objects.get(student__enrollment_no="1002")
    assert (result.correct, result.error_kind, result.student.first_name) == (True, "", "عبدالله")


def test_teacher_reads_their_section_with_error_kind_counts(teacher_client, item, wrong):
    post(teacher_client, batch(item, wrong))
    response = teacher_client.get(URL, {"section": SECTION})
    assert response.status_code == 200 and response["Cache-Control"] == "private, no-store"
    data = response.json()
    kind = item.options[wrong].kind
    assert (data["attempted"], data["correct"]) == (2, 1)
    assert data["kinds"] == [{"kind": kind, "label": ERROR_KINDS[kind], "count": 1}]
    assert [s["enrollment_no"] for s in data["students"]] == ["1001", "1002"]
    assert data["students"][1]["results"] == [
        {
            "example": EXAMPLE,
            "seed": SEED,
            "choice": wrong,
            "correct": False,
            "error_kind": kind,
            "misconception": ERROR_KINDS[kind],
        }
    ]


def test_other_teacher_gets_403(teacher_client, other_client, item, wrong):
    """معلم آخر بصلاحية المعلم يطلب شعبة ليست له: 403 بلا أي بيان، ورده لا يختلف عن شعبة لا وجود لها."""
    post(teacher_client, batch(item, wrong))
    response = other_client.get(URL, {"section": SECTION})
    assert response.status_code == 403
    assert FIRST not in response.content.decode() and "1001" not in response.content.decode()
    assert other_client.get(URL, {"section": "لا-شعبة"}).content == response.content
    assert AuditLog.objects.filter(action="results.denied", actor__username="teacher2").count() == 2
    assert not AuditLog.objects.filter(action="results.read").exists()


def test_same_section_name_is_a_separate_roster_for_each_teacher(teacher_client, other_client, item, wrong):
    """اسم الشعبة في مساحة مالكها: إدخال معلم آخر بالاسم نفسه لا يمسّ طلاب الأول ولا يكشفهم."""
    post(teacher_client, batch(item, wrong))
    theirs = {"section": SECTION, "results": [row("1001", wrong, "ناصر", "الكواري")]}
    assert post(other_client, theirs).status_code == 200
    assert SectionStudent.objects.filter(enrollment_no="1001").count() == 2
    data = other_client.get(URL, {"section": SECTION}).json()
    assert [(s["enrollment_no"], s["first_name"]) for s in data["students"]] == [("1001", "ناصر")]
    mine = teacher_client.get(URL, {"section": SECTION}).json()
    assert [s["first_name"] for s in mine["students"]] == [FIRST, SECOND_FIRST]
    assert selectors.owned_sections(SectionStudent.objects.first().owner) == [SECTION]


def test_entry_and_read_are_audited_without_student_names(teacher_client, item, wrong):
    post(teacher_client, batch(item, wrong))
    post(teacher_client, batch(item, wrong))
    teacher_client.get(URL, {"section": SECTION})
    target = f"{GRADE10_SLUG}/{LESSON}@{SECTION}"
    written = AuditLog.objects.filter(action="results.record", target=target).order_by("created_at", "id")
    assert [log.payload for log in written] == [
        {"students": 2, "results": 2, "created": 2, "updated": 0},
        {"students": 2, "results": 2, "created": 0, "updated": 0},
    ]
    read = AuditLog.objects.get(action="results.read", target=target)
    assert read.payload == {"students": 2, "results": 2}
    assert {log.actor.get_username() for log in (*written, read)} == {"teacher"}
    logged = json.dumps(
        list(AuditLog.objects.filter(action__startswith="results.").values("target", "payload")),
        ensure_ascii=False,
    )
    for private in (FIRST, LAST, SECOND_FIRST, SECOND_LAST, "1001", "1002"):
        assert private not in logged


@pytest.mark.parametrize(
    "bad",
    [
        {"first_name": "سالم بن محمد بن علي"},  # اسم رباعي في خانة الاسم الأول
        {"last_name": "   "},
        {"first_name": "س" * 31},
        {"enrollment_no": "10 01"},
        {"enrollment_no": ""},
        {"example": 99},  # لا بند لهذا المثال في بنك الدرس
        {"choice": OPTION_COUNT},
        {"seed": -1},
    ],
)
def test_invalid_entry_rejects_the_whole_batch(teacher_client, item, bad):
    payload = {"section": SECTION, "results": [row("1001", item.answer_index), {**row("1002", 0), **bad}]}
    assert post(teacher_client, payload).status_code == 422
    assert not SectionStudent.objects.exists() and not ItemResult.objects.exists()
    assert not AuditLog.objects.filter(action="results.record").exists()


def test_conflicting_rows_in_one_batch_are_rejected(item, wrong):
    same_item = [Entry("1001", FIRST, LAST, EXAMPLE, SEED, item.answer_index)] * 2
    assert len(item_results.clean_entries(same_item)) == 1
    with pytest.raises(ResultsError, match="خياران"):
        item_results.clean_entries([same_item[0], Entry("1001", FIRST, LAST, EXAMPLE, SEED, wrong)])
    with pytest.raises(ResultsError, match="باسمين"):
        item_results.clean_entries([same_item[0], Entry("1001", "ناصر", LAST, EXAMPLE, SEED + 1, wrong)])
    with pytest.raises(ResultsError, match="لا نتائج"):
        item_results.clean_entries([])


def test_unknown_course_or_lesson_is_404(teacher_client, item):
    payload = {"section": SECTION, "results": [row("1001", item.answer_index)]}
    assert post(teacher_client, payload, f"/api/v1/results/{GRADE10_SLUG}/9.9").status_code == 404
    assert post(teacher_client, payload, f"/api/v1/results/no-such-course/{LESSON}").status_code == 404
    post(teacher_client, payload)
    assert teacher_client.get(f"/api/v1/results/{GRADE10_SLUG}/9.9", {"section": SECTION}).status_code == 404


def test_student_holds_only_enrollment_number_and_short_name():
    """تقليل البيانات: لا حقل في نموذج الطالب غير المالك والشعبة ورقم القيد والاسمين (وطوابع الوقت)."""
    fields = {f.name for f in SectionStudent._meta.get_fields() if not f.auto_created}
    assert fields == {
        "owner",
        "section",
        "enrollment_no",
        "first_name",
        "last_name",
        "created_at",
        "updated_at",
    }
    assert FIRST not in str(SectionStudent(section=SECTION, enrollment_no="1001", first_name=FIRST))
    assert (models.ENROLLMENT_LENGTH, models.STUDENT_NAME_LENGTH, models.ITEM_OPTION_COUNT) == (
        item_results.ENROLLMENT_LENGTH,
        item_results.NAME_LENGTH,
        OPTION_COUNT,
    )


def test_database_rejects_a_kind_on_a_correct_result(teacher_client, item, wrong):
    post(teacher_client, batch(item, wrong))
    with pytest.raises(IntegrityError), transaction.atomic():
        ItemResult.objects.filter(correct=True).update(error_kind="sign")
    with pytest.raises(IntegrityError), transaction.atomic():
        ItemResult.objects.filter(correct=False).update(error_kind="")


# ───── الاحتفاظ حتى نهاية العام الدراسي ─────

ENDED_YEAR = "2025-2026"


@pytest.fixture
def ended_lesson():
    """درس في مقرر سنة أكاديمية انتهى تقويمها."""
    calendar = AcademicCalendar.objects.create(year=ENDED_YEAR, weekdays=["sun"])
    CalendarTerm.objects.create(
        calendar=calendar, semester=1, start=date(2025, 8, 24), end=date(2025, 12, 18)
    )
    CalendarTerm.objects.create(calendar=calendar, semester=2, start=date(2026, 1, 4), end=date(2026, 6, 11))
    current = Course.objects.get(slug=GRADE10_SLUG)
    course = Course.objects.create(
        slug="g10-s1-2025",
        title="العاشر 2025-2026",
        grade=current.grade,
        track=current.track,
        semester=current.semester,
        academic_year=ENDED_YEAR,
        edition=current.edition,
    )
    return Lesson.objects.create(course=course, code=LESSON, title="درس سنة منتهية", unit=1)


def test_purge_removes_only_ended_year_results_and_keeps_aggregates(
    teacher_client, item, wrong, ended_lesson, monkeypatch
):
    post(teacher_client, batch(item, wrong))
    teacher = SectionStudent.objects.first().owner
    kept = SectionStudent.objects.get(enrollment_no="1001")  # له نتيجة في السنة الجارية والمنتهية معًا
    gone = SectionStudent.objects.create(
        owner=teacher, section="10/1", enrollment_no="0900", first_name="حمد", last_name="النعيمي"
    )
    for student in (kept, gone):
        ItemResult.objects.create(
            student=student,
            lesson=ended_lesson,
            example=1,
            seed=0,
            choice=1,
            correct=False,
            error_kind="sign",
        )
    services.record_outcome(teacher, SECTION, ClassOutcome(LESSON, 30, 12))
    ClassOutcomeRecord.objects.create(
        owner=teacher, section="10/1", lesson=ended_lesson, attempted=28, correct=20
    )
    today = date(2026, 11, 25)

    preview = services.purge_ended_results(today, write=False)
    assert (preview.years, preview.students, preview.results) == ((ENDED_YEAR,), 1, 2)
    assert ItemResult.objects.count() == 4

    monkeypatch.setattr(services.timezone, "localdate", lambda: today)
    call_command("purge_student_results")
    assert not ItemResult.objects.filter(lesson=ended_lesson).exists()
    assert not SectionStudent.objects.filter(pk=gone.pk).exists()
    assert ItemResult.objects.filter(lesson__course__slug=GRADE10_SLUG).count() == 2
    assert set(SectionStudent.objects.values_list("enrollment_no", flat=True)) == {"1001", "1002"}
    assert ClassOutcomeRecord.objects.count() == 2
    assert ClassOutcomeRecord.objects.get(lesson=ended_lesson).correct == 20
    log = AuditLog.objects.get(action="results.purge")
    assert (log.target, log.payload) == (ENDED_YEAR, {"students": 1, "results": 2})

    again = services.purge_ended_results(today)
    assert (again.students, again.results) == (0, 0)
    assert AuditLog.objects.filter(action="results.purge").count() == 1


def test_purge_command_keeps_a_year_that_has_not_ended(teacher_client, item, wrong, capsys, monkeypatch):
    """سنة المقرر حتى آخر يوم في تقويمها لا يُحذف منها شيء، والأمر يعمل مرتين بلا أثر؛ وفي اليوم التالي تُعدّ منتهية."""
    post(teacher_client, batch(item, wrong))
    year = Course.objects.get(slug=GRADE10_SLUG).academic_year
    last_day = max(CalendarTerm.objects.filter(calendar__year=year).values_list("end", flat=True))
    assert year not in services.curriculum.ended_academic_years(last_day)
    assert year in services.curriculum.ended_academic_years(last_day + timedelta(days=1))
    monkeypatch.setattr(services.timezone, "localdate", lambda: last_day)
    call_command("purge_student_results", "--dry-run")
    call_command("purge_student_results")
    assert ItemResult.objects.count() == 2 and SectionStudent.objects.count() == 2
    assert capsys.readouterr().out.strip()
