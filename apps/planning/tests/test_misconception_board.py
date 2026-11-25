"""تشخيص الخطأ: لوحة سوء الفهم للشعبة والدرس (M1.3).

أعداد اللوحة تطابق نتائج مدخلة معروفة (الطالب المكرر الخطأ يُعدّ مرة)، والقراءة باستعلامات مجمَّعة لا تزيد بعدد الطلاب،
والمعلم لا يرى إلا شعبه، وسجل التدقيق أعداد بلا أسماء ولا أرقام قيد.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.core.models import AuditLog
from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import Lesson
from apps.papers.access import ensure_teacher
from apps.papers.domain.generators import ERROR_KINDS
from apps.planning import selectors
from apps.planning.models import ItemResult, SectionStudent

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("loaded_courses")]

LESSON, OTHER_LESSON = "1.1", "1.2"
SECTION, OTHER_SECTION = "10/3", "10/1"
URL = f"/api/v1/misconceptions/{GRADE10_SLUG}/{LESSON}"
PASSWORD = "Rasm-Bayani-2026"  # pragma: allowlist secret
ROSTER = {
    "1001": ("سالم", "المري"),
    "1002": ("عبد الله", "آل ثاني"),
    "1003": ("ناصر", "الكواري"),
    "1004": ("حمد", "النعيمي"),
    "1005": ("جاسم", "السليطي"),
}
# (رقم القيد، المثال، البذرة، نوع الخطأ أو فارغ للصحيح) في الدرس LESSON
RESULTS = [
    ("1001", 1, 0, "sign"),
    ("1001", 1, 1, "sign"),  # النوع نفسه في المثال نفسه ببذرة أخرى
    ("1001", 2, 0, "sign"),  # والنوع نفسه في مثال آخر: الطالب يُعدّ مرة
    ("1002", 1, 0, "sign"),
    ("1002", 3, 0, "swap"),  # نوعان لطالب واحد: يظهر في كليهما
    ("1003", 1, 0, ""),
    ("1003", 2, 0, ""),
    ("1005", 1, 0, ""),
    ("1005", 2, 0, "concept"),
]  # و1004 بلا نتيجة


def lesson_of(code: str) -> Lesson:
    return Lesson.objects.get(course__slug=GRADE10_SLUG, code=code)


def enroll(owner, section: str, roster: dict) -> dict[str, SectionStudent]:
    return {
        no: SectionStudent.objects.create(
            owner=owner, section=section, enrollment_no=no, first_name=first, last_name=last
        )
        for no, (first, last) in roster.items()
    }


def answer(student: SectionStudent, lesson: Lesson, example: int, seed: int, kind: str) -> None:
    ItemResult.objects.create(
        student=student,
        lesson=lesson,
        example=example,
        seed=seed,
        choice=0,
        correct=not kind,
        error_kind=kind,
    )


@pytest.fixture
def teacher(teacher_client):
    return get_user_model().objects.get(username="teacher")


@pytest.fixture
def entered(teacher):
    """نتائج معروفة لشعبة المعلم في الدرس، ومعها ما يجب ألا يدخل اللوحة: درس آخر وشعبة أخرى."""
    students = enroll(teacher, SECTION, ROSTER)
    lesson = lesson_of(LESSON)
    for no, example, seed, kind in RESULTS:
        answer(students[no], lesson, example, seed, kind)
    answer(students["1003"], lesson_of(OTHER_LESSON), 1, 0, "formula")
    elsewhere = enroll(teacher, OTHER_SECTION, {"2001": ("خالد", "المهندي")})
    answer(elsewhere["2001"], lesson, 1, 0, "square")
    return students


@pytest.fixture
def other_client(db):
    """معلم ثانٍ بصلاحية المعلم كاملة: الرفض لأن الشعبة ليست له لا لنقص صلاحية."""
    other, _ = ensure_teacher("teacher2", PASSWORD)
    client = Client()
    client.force_login(other)
    return client


def test_counts_match_results(teacher_client, entered):
    response = teacher_client.get(URL, {"section": SECTION})
    assert response.status_code == 200 and response["Cache-Control"] == "private, no-store"
    board = response.json()
    assert (board["students"], board["entered"], board["correct"], board["missing"]) == (5, 4, 1, 1)
    # تنازليًا بالعدد، والتساوي بترتيب ERROR_KINDS (swap قبل concept)
    assert [(k["kind"], k["label"], k["count"]) for k in board["kinds"]] == [
        ("sign", ERROR_KINDS["sign"], 2),
        ("swap", ERROR_KINDS["swap"], 1),
        ("concept", ERROR_KINDS["concept"], 1),
    ]
    sign, swap, concept = board["kinds"]
    assert sign["examples"] == [1, 2]
    assert sign["students"] == [
        {"enrollment_no": "1001", "first_name": "سالم", "last_name": "المري", "examples": [1, 2]},
        {"enrollment_no": "1002", "first_name": "عبد الله", "last_name": "آل ثاني", "examples": [1]},
    ]
    assert [s["enrollment_no"] for s in swap["students"]] == ["1002"] and swap["examples"] == [3]
    assert [s["enrollment_no"] for s in concept["students"]] == ["1005"] and concept["examples"] == [2]
    # الأعداد مشتقة من الصفوف المدخلة نفسها: طلاب مختلفون لكل نوع
    expected = {}
    for no, _example, _seed, kind in RESULTS:
        if kind:
            expected.setdefault(kind, set()).add(no)
    assert {k["kind"]: k["count"] for k in board["kinds"]} == {k: len(v) for k, v in expected.items()}
    assert all(k["count"] == len(k["students"]) for k in board["kinds"])


def test_board_reads_with_grouped_queries_whatever_the_roster_size(teacher, entered):
    """لا استعلام لكل طالب: عدد الاستعلامات لا يتغير حين تتضاعف الشعبة ونتائجها."""

    def queries() -> int:
        with CaptureQueriesContext(connection) as captured:
            selectors.misconception_board(teacher, GRADE10_SLUG, LESSON, SECTION)
        return len(captured)

    before = queries()
    lesson = lesson_of(LESSON)
    more = enroll(teacher, SECTION, {str(3000 + i): ("طالب", "جديد") for i in range(30)})
    for i, student in enumerate(more.values()):
        answer(student, lesson, 1, 0, list(ERROR_KINDS)[i % len(ERROR_KINDS)])
    assert queries() == before <= 5
    board = selectors.misconception_board(teacher, GRADE10_SLUG, LESSON, SECTION)
    assert (board["students"], board["entered"], board["missing"]) == (35, 34, 1)


def test_section_without_results_is_an_empty_board(teacher_client, teacher):
    enroll(teacher, SECTION, ROSTER)
    board = teacher_client.get(URL, {"section": SECTION}).json()
    assert (board["students"], board["entered"], board["correct"], board["missing"]) == (5, 0, 0, 5)
    assert board["kinds"] == []


def test_other_teacher_gets_403(teacher_client, other_client, entered):
    """معلم آخر بصلاحية المعلم يطلب لوحة شعبة ليست له: 403 بلا أي بيان، ورده لا يختلف عن شعبة لا وجود لها."""
    response = other_client.get(URL, {"section": SECTION})
    assert response.status_code == 403
    body = response.content.decode()
    assert "سالم" not in body and "1001" not in body
    assert other_client.get(URL, {"section": "لا-شعبة"}).content == response.content
    assert AuditLog.objects.filter(action="misconceptions.denied", actor__username="teacher2").count() == 2
    assert not AuditLog.objects.filter(action="misconceptions.read").exists()


def test_board_requires_a_session_and_the_teacher_permission(outsider_client):
    assert Client().get(URL, {"section": SECTION}).status_code == 401
    assert outsider_client.get(URL, {"section": SECTION}).status_code == 403
    assert Client().get("/api/v1/results/sections").status_code == 401


def test_unknown_lesson_is_404(teacher_client, entered):
    url = f"/api/v1/misconceptions/{GRADE10_SLUG}/9.9"
    assert teacher_client.get(url, {"section": SECTION}).status_code == 404


def test_audit_log_has_counts_without_names(teacher_client, entered):
    teacher_client.get(URL, {"section": SECTION})
    log = AuditLog.objects.get(action="misconceptions.read")
    assert log.target == f"{GRADE10_SLUG}/{LESSON}@{SECTION}"
    assert log.actor.get_username() == "teacher"
    assert log.payload == {
        "students": 5,
        "entered": 4,
        "correct": 1,
        "kinds": {"sign": 2, "swap": 1, "concept": 1},
    }
    logged = json.dumps(
        list(AuditLog.objects.filter(action__startswith="misconceptions.").values("target", "payload")),
        ensure_ascii=False,
    )
    for no, names in ROSTER.items():
        for private in (no, *names):
            assert private not in logged


def test_teacher_lists_only_their_sections(teacher_client, other_client, entered):
    assert teacher_client.get("/api/v1/results/sections").json() == [OTHER_SECTION, SECTION]
    assert other_client.get("/api/v1/results/sections").json() == []
