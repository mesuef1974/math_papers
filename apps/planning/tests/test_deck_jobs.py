"""عروض الدروس من الأصول المنشورة: شرط انتهاء المرحلة 4 (الدروس الـ19 بعدد شرائح يطابق أمثلتها) والمهمة والواجهة."""

import io
import zipfile

import pytest

from apps.assets.models import Asset
from apps.assets.storage import get_storage
from apps.assets.tests.conftest import make_png
from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import Lesson
from apps.knowledge.selectors import course_index
from apps.knowledge.services import load_course
from apps.planning import selectors, services
from apps.planning.domain.deck import DeckError
from apps.planning.tasks import build_lesson_deck_task

pytestmark = pytest.mark.django_db
API = "/api/v1/decks"


def _slides(data: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return sorted(n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml"))


def _publish(lesson_code: str, numbers: list[int], with_cont: tuple[int, ...] = ()) -> None:
    lesson = Lesson.objects.get(course__slug=GRADE10_SLUG, code=lesson_code)
    for number in numbers:
        for part in (0, 1) if number in with_cont else (0,):
            png = make_png(60 + number, 40 + part, shade=number * 7 + part)
            storage_key = f"assets/{GRADE10_SLUG}/{lesson_code}/example{number}-{part}-test.png"
            get_storage().put(storage_key, png, "image/png")
            Asset.objects.create(
                course=lesson.course,
                lesson=lesson,
                kind=Asset.Kind.EXAMPLE,
                number=number,
                part=part,
                key=storage_key,
                sha256=f"{lesson_code}-{number}-{part}".ljust(64, "0"),
                size=len(png),
                width=60 + number,
                height=40 + part,
            )


@pytest.fixture
def g10(db):
    load_course(GRADE10_SLUG)


def test_every_grade10_lesson_builds_a_deck_matching_its_examples(g10):
    lessons = [lesson for lesson in course_index(GRADE10_SLUG).lessons if lesson.examples]
    assert len(lessons) == 19
    for lesson in lessons:
        _publish(lesson.lesson, [e.n for e in lesson.examples])
    for lesson in lessons:
        key = services.build_lesson_deck(GRADE10_SLUG, lesson.lesson, 45)
        data = get_storage().get(key)
        examples = len(lesson.examples)
        # عنوان + أمثلة + سير الحصة (+ التقويم إن وُجدت أعماق لاختبار الدرس)
        assert len(_slides(data)) == 1 + examples + 1 + (1 if lesson.quiz_depths else 0), lesson.lesson


def test_continuation_clips_get_their_own_slides(g10):
    _publish("2.6", [1, 2], with_cont=(2,))
    key = services.build_lesson_deck(GRADE10_SLUG, "2.6", 45)
    lesson = next(item for item in course_index(GRADE10_SLUG).lessons if item.lesson == "2.6")
    assert len(_slides(get_storage().get(key))) == 1 + 3 + 1 + (1 if lesson.quiz_depths else 0)


def test_build_is_idempotent_and_key_follows_inputs(g10):
    _publish("2.6", [1])
    first = services.build_lesson_deck(GRADE10_SLUG, "2.6", 45)
    bytes_first = get_storage().get(first)
    assert services.build_lesson_deck(GRADE10_SLUG, "2.6", 45) == first
    assert get_storage().get(first) == bytes_first
    assert services.prepare_deck(GRADE10_SLUG, "2.6", 60) != first
    Asset.objects.filter(lesson__code="2.6").update(sha256="f" * 64)
    assert services.prepare_deck(GRADE10_SLUG, "2.6", 45) != first


@pytest.mark.parametrize(
    ("lesson", "period"),
    [("2.6", 10), ("9.9", 45), ("2.6", 45)],  # زمن خارج المدى، درس مجهول، لا مقاطع منشورة
)
def test_invalid_requests_are_rejected_before_any_work(g10, lesson, period):
    with pytest.raises(DeckError):
        services.prepare_deck(GRADE10_SLUG, lesson, period)


def test_failure_is_recorded_and_visible(g10, monkeypatch):
    _publish("2.6", [1])
    key = services.prepare_deck(GRADE10_SLUG, "2.6", 45)

    def boom(*args, **kwargs):
        raise DeckError("مقطع تالف")

    monkeypatch.setattr(services, "build_pptx", boom)
    with pytest.raises(DeckError):
        services.build_lesson_deck(GRADE10_SLUG, "2.6", 45)
    assert services.deck_state(key) == ("failed", "مقطع تالف")
    services.clear_deck_failure(key)
    assert services.deck_state(key) == ("pending", "")


def test_lessons_listing_counts_examples_not_continuations(g10):
    _publish("1.1", [1, 2], with_cont=(2,))
    title = Lesson.objects.get(course__slug=GRADE10_SLUG, code="1.1").title
    assert selectors.deck_lessons(GRADE10_SLUG) == [
        {"lesson": "1.1", "title": title, "examples": 2, "clips": 3}
    ]


def test_task_runs_in_place_and_returns_key(g10):
    _publish("2.6", [1])
    key = build_lesson_deck_task.delay(GRADE10_SLUG, "2.6", 45).get()
    assert services.deck_state(key) == ("ready", "")


# ───── الواجهة ─────
def test_api_requires_login(client):
    assert client.get(f"{API}/lessons?course={GRADE10_SLUG}").status_code == 401


def test_api_outsider_is_forbidden(outsider_client):
    assert outsider_client.get(f"{API}/lessons?course={GRADE10_SLUG}").status_code == 403


def test_api_request_status_download_flow(teacher_client, g10):
    _publish("2.6", [1, 2])
    listing = teacher_client.get(f"{API}/lessons?course={GRADE10_SLUG}").json()
    assert [(r["lesson"], r["examples"]) for r in listing] == [("2.6", 2)]
    body = {"course": GRADE10_SLUG, "lesson": "2.6", "period_minutes": 45}
    posted = teacher_client.post(f"{API}/", body, content_type="application/json")
    assert posted.status_code == 200 and posted.json()["status"] == "ready"
    query = f"course={GRADE10_SLUG}&lesson=2.6&period_minutes=45"
    assert teacher_client.get(f"{API}/status?{query}").json()["status"] == "ready"
    response = teacher_client.get(f"{API}/download?{query}")
    assert response.status_code == 200
    assert response["Content-Type"] == selectors.PPTX_CONTENT_TYPE
    assert "attachment" in response["Content-Disposition"]
    assert zipfile.is_zipfile(io.BytesIO(response.content))


def test_api_download_before_build_is_404_and_bad_input_422(teacher_client, g10):
    _publish("2.6", [1])
    query = f"course={GRADE10_SLUG}&lesson=2.6&period_minutes=45"
    assert teacher_client.get(f"{API}/download?{query}").status_code == 404
    bad = {"course": GRADE10_SLUG, "lesson": "2.6", "period_minutes": 5}
    assert teacher_client.post(f"{API}/", bad, content_type="application/json").status_code == 422
