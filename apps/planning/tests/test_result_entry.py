"""تشخيص الخطأ: إدخال نتائج الطلاب من الواجهة (M1.4).

مسار البنود يعيد بطاقة الخروج نفسها التي في عرض الحصة (المثال والبذرة والنص) من مصدر واحد (`check_items.period_items`)
وبلا كشف الصحيح، وما يُدخله المعلم بتلك البذور يُحفظ بالمسار القائم ويظهر في لوحة سوء الفهم، وطلاب الشعبة لا يقرؤهم غير
مالكها.
"""

import json

import pytest
from django.test import Client

from apps.curriculum.courses import GRADE10_SLUG
from apps.papers.access import ensure_teacher
from apps.papers.domain.bidi import strip_isolation
from apps.papers.domain.generators import ERROR_KINDS
from apps.papers.domain.item_bank import exit_ticket
from apps.planning.domain.check_items import OPTION_LETTERS, period_items
from apps.planning.domain.deck import ExampleClip, build_period_deck
from apps.planning.domain.slide_math import display
from apps.planning.models import ItemResult
from apps.planning.selectors import lesson_preps

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("loaded_courses")]

SECTION = "10/3"
PASSWORD = "Rasm-Bayani-2026"  # pragma: allowlist secret
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
PUBLIC_FIELDS = {"k", "n", "example", "page", "seed", "stem", "options"}


def items_url(lesson: str, course: str = GRADE10_SLUG) -> str:
    return f"/api/v1/results/{course}/{lesson}/items"


def results_url(lesson: str) -> str:
    return f"/api/v1/results/{GRADE10_SLUG}/{lesson}"


@pytest.fixture
def lesson_periods():
    """حصص أول درس في الخطة له بطاقة خروج ببند من البنك: (رمز الدرس، تحضيرات حصصه كلها)."""
    by_lesson: dict[str, list] = {}
    for row in lesson_preps(GRADE10_SLUG):
        by_lesson.setdefault(row.prep.lesson, []).append(row.prep)
    return next(
        (code, preps)
        for code, preps in by_lesson.items()
        if any(period_items(prep).exit is not None for prep in preps)
    )


@pytest.fixture
def other_client(db):
    """معلم ثانٍ بصلاحية المعلم كاملة: الرفض لأن الشعبة ليست له لا لنقص صلاحية."""
    teacher, _ = ensure_teacher("teacher2", PASSWORD)
    client = Client()
    client.force_login(teacher)
    return client


def exit_slide(prep):
    clips = tuple(
        ExampleClip(n=e.n, png=PNG, width_px=1600, height_px=900, part=part)
        for e in prep.examples
        for part in range(1, (e.continuations or 1) + 1)
    )
    return next(s for s in build_period_deck(prep, clips).slides if s.kind == "exit")


def test_entry_items_match_exit_ticket(teacher_client, lesson_periods):
    lesson, preps = lesson_periods
    response = teacher_client.get(items_url(lesson))
    assert response.status_code == 200, response.content
    data = response.json()
    assert (data["course"], data["lesson"]) == (GRADE10_SLUG, lesson)
    shown = {prep.k: prep for prep in preps if period_items(prep).exit is not None}
    assert [item["k"] for item in data["items"]] == sorted(shown)
    for item in data["items"]:
        prep = shown[item["k"]]
        ticket = period_items(prep)
        # المثال والبذرة هما ما ولّد بند العرض والتحضير: البنك يعيد بهما البند نفسه
        assert item["example"] == prep.exit_ticket.example
        assert item["seed"] == ticket.exit_seed
        assert exit_ticket(GRADE10_SLUG, lesson, item["example"], seed=item["seed"]) == ticket.exit
        # والنص هو نص شريحة الخروج: السؤال ثم الخيارات الأربعة بترتيبها
        bullets = exit_slide(prep).bullets
        assert strip_isolation(item["stem"]) == strip_isolation(display(bullets[0]))
        assert [strip_isolation(display(b)) for b in bullets[1:]] == [
            strip_isolation(f"{OPTION_LETTERS[i]}) {text}") for i, text in enumerate(item["options"])
        ]
        # لا شيء في الرد يدل على الصحيح ولا على نوع الخطأ
        assert set(item) == PUBLIC_FIELDS
    body = response.content.decode()
    assert "correct" not in body and "kind" not in body and "misconception" not in body


def test_entry_items_require_a_session_and_the_teacher_permission(outsider_client, lesson_periods):
    lesson, _ = lesson_periods
    assert Client().get(items_url(lesson)).status_code == 401
    assert outsider_client.get(items_url(lesson)).status_code == 403


def test_unknown_lesson_or_course_is_404(teacher_client):
    assert teacher_client.get(items_url("9.9")).status_code == 404
    assert teacher_client.get(items_url("1.1", "no-such-course")).status_code == 404


def test_entered_choices_are_saved_and_reach_the_board(teacher_client, other_client, lesson_periods):
    """ما يرسله جدول الإدخال (بذور مسار البنود ورقم الخيار وحده) يُحفظ مصحَّحًا من البنك ويظهر في لوحة سوء الفهم."""
    lesson, _ = lesson_periods
    shown = teacher_client.get(items_url(lesson)).json()["items"][0]
    item = exit_ticket(GRADE10_SLUG, lesson, shown["example"], seed=shown["seed"])
    wrong = next(i for i, option in enumerate(item.options) if not option.correct)
    kind = item.options[wrong].kind

    def row(enrollment_no: str, first: str, last: str, choice: int) -> dict:
        return {
            "enrollment_no": enrollment_no,
            "first_name": first,
            "last_name": last,
            "example": shown["example"],
            "seed": shown["seed"],
            "choice": choice,
        }

    payload = {
        "section": SECTION,
        "results": [row("1001", "سالم", "المري", item.answer_index), row("1002", "ناصر", "الكواري", wrong)],
    }
    saved = teacher_client.post(
        results_url(lesson), data=json.dumps(payload), content_type="application/json"
    )
    assert saved.status_code == 200, saved.content
    assert saved.json() == {"students": 2, "results": 2, "created": 2, "updated": 0}
    assert ItemResult.objects.get(student__enrollment_no="1002").error_kind == kind

    # إعادة فتح الجدول: طلاب الشعبة واختياراتهم المحفوظة بالمثال والبذرة نفسيهما
    reopened = teacher_client.get(results_url(lesson), {"section": SECTION}).json()
    assert [(s["enrollment_no"], s["first_name"], s["last_name"]) for s in reopened["students"]] == [
        ("1001", "سالم", "المري"),
        ("1002", "ناصر", "الكواري"),
    ]
    assert [(r["example"], r["seed"], r["choice"]) for r in reopened["students"][1]["results"]] == [
        (shown["example"], shown["seed"], wrong)
    ]

    board = teacher_client.get(f"/api/v1/misconceptions/{GRADE10_SLUG}/{lesson}", {"section": SECTION}).json()
    assert (board["students"], board["entered"], board["correct"], board["missing"]) == (2, 2, 1, 0)
    assert [(k["kind"], k["label"], k["count"]) for k in board["kinds"]] == [(kind, ERROR_KINDS[kind], 1)]
    assert board["kinds"][0]["students"] == [
        {
            "enrollment_no": "1002",
            "first_name": "ناصر",
            "last_name": "الكواري",
            "examples": [shown["example"]],
        }
    ]

    # معلم آخر لا يقرأ طلاب الشعبة لتعبئة جدوله: 403 بلا أي بيان
    denied = other_client.get(results_url(lesson), {"section": SECTION})
    assert denied.status_code == 403
    assert "سالم" not in denied.content.decode() and "1001" not in denied.content.decode()
