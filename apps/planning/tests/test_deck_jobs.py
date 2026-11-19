"""عروض الحصص من الأصول المنشورة: شرط انتهاء المرحلة 4 (48 عرضًا تجتاز المعايير الحاجبة بعدد شرائح أمثلة يطابق تحضيرها
وتتماته) والمهمة الخلفية والواجهة البرمجية."""

import hashlib
import io
import zipfile

import pytest

from apps.assets.models import Asset
from apps.assets.storage import get_storage
from apps.assets.tests.conftest import make_png
from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import Lesson
from apps.planning import selectors, services
from apps.planning.domain.deck import DeckError
from apps.planning.tasks import build_period_deck_task

pytestmark = pytest.mark.django_db
API = "/api/v1/decks"


def _slides(data: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return [n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]


def _clip_slides(data: bytes) -> int:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return sum(
            'name="مقطع' in z.read(n).decode("utf-8")
            for n in z.namelist()
            if n.startswith("ppt/slides/slide")
        )


def _publish(lesson_code: str, examples) -> None:
    """مقطع لكل مثال وتتماته بدقة تجتاز S7؛ التجزئة المخزَّنة تجزئة الصورة نفسها كما يكتبها النشر."""
    lesson = Lesson.objects.get(course__slug=GRADE10_SLUG, code=lesson_code)
    for e in examples:
        for part in range(e.continuations or 1):
            if Asset.objects.filter(lesson=lesson, kind=Asset.Kind.EXAMPLE, number=e.n, part=part).exists():
                continue
            png = make_png(1600, 900, shade=e.n * 7 + part)
            sha = hashlib.sha256(png).hexdigest()
            key = f"assets/{GRADE10_SLUG}/{lesson_code}/example{e.n}-{part}-{sha[:16]}.png"
            get_storage().put(key, png, "image/png")
            Asset.objects.create(
                course=lesson.course,
                lesson=lesson,
                kind=Asset.Kind.EXAMPLE,
                number=e.n,
                part=part,
                key=key,
                sha256=sha,
                size=len(png),
                width=1600,
                height=900,
            )


@pytest.fixture
def preps(loaded_courses):
    return selectors.lesson_preps(GRADE10_SLUG)


@pytest.fixture
def period(preps):
    """أول حصة فيها أمثلة، بمقاطعها منشورة."""
    item = next(p for p in preps if p.prep.examples)
    _publish(item.prep.lesson, item.prep.examples)
    return item.prep


def test_forty_eight_periods_build_decks_matching_their_preps(preps):
    assert len(preps) == 48
    for item in preps:
        _publish(item.prep.lesson, item.prep.examples)
    for item in preps:
        prep = item.prep
        key = services.build_period_deck_file(GRADE10_SLUG, prep.lesson, prep.k)
        assert services.deck_state(key) == ("ready", ""), key
        data = get_storage().get(key)
        clips = sum(e.continuations or 1 for e in prep.examples)
        # مقاطع كل مثال وتتماته ثم شريحة كشف حله
        assert _clip_slides(data) == clips + len(prep.examples), key


def test_course_decks_command_prints_one_line_and_fails_on_low_resolution_clips(preps, capsys):
    from django.core.management import CommandError, call_command

    for item in preps:
        _publish(item.prep.lesson, item.prep.examples)
    call_command("build_period_decks", GRADE10_SLUG)
    assert capsys.readouterr().out.strip() == "ناجح 48 فاشل 0"
    assert services.build_course_decks(GRADE10_SLUG) == (48, ())  # idempotent
    # مقطع بدقة دون S7 يُفشل حصته وحدها، والسطر يعدّها
    item = next(p for p in preps if p.prep.examples)
    asset = Asset.objects.filter(lesson__code=item.prep.lesson, number=item.prep.examples[0].n, part=0).get()
    png = make_png(400, 225, shade=3)
    asset.sha256, asset.width, asset.height = hashlib.sha256(png).hexdigest(), 400, 225
    asset.save()
    get_storage().put(asset.key, png, "image/png")
    with pytest.raises(CommandError, match="ناجح 47 فاشل 1"):
        call_command("build_period_decks", GRADE10_SLUG)
    assert "S7" in capsys.readouterr().err
    with pytest.raises(CommandError, match="لا خطة فصلية"):
        call_command("build_period_decks", "unknown")


def test_build_is_idempotent_and_key_follows_inputs(period):
    first = services.build_period_deck_file(GRADE10_SLUG, period.lesson, period.k)
    stored = get_storage().get(first)
    assert services.build_period_deck_file(GRADE10_SLUG, period.lesson, period.k) == first
    assert get_storage().get(first) == stored
    assert first.startswith(f"decks/{GRADE10_SLUG}/{period.lesson}-k{period.k}of{period.n}-p45-")
    Asset.objects.filter(lesson__code=period.lesson, number=period.examples[0].n).update(sha256="f" * 64)
    assert services.prepare_deck(GRADE10_SLUG, period.lesson, period.k) != first


def test_unknown_period_and_missing_clips_are_rejected_before_any_work(preps):
    with pytest.raises(selectors.PrepNotFoundError):
        services.prepare_deck(GRADE10_SLUG, "9.9", 1)
    with pytest.raises(selectors.PrepNotFoundError):
        services.prepare_deck(GRADE10_SLUG, preps[0].prep.lesson, 99)
    item = next(p for p in preps if p.prep.examples)
    with pytest.raises(DeckError, match="لا مقاطع منشورة"):
        services.prepare_deck(GRADE10_SLUG, item.prep.lesson, item.prep.k)


def test_failure_is_recorded_and_visible(period, monkeypatch):
    key = services.prepare_deck(GRADE10_SLUG, period.lesson, period.k)

    def boom(*args, **kwargs):
        raise DeckError("مقطع تالف")

    monkeypatch.setattr(services, "build_period_pptx", boom)
    with pytest.raises(DeckError):
        services.build_period_deck_file(GRADE10_SLUG, period.lesson, period.k)
    assert services.deck_state(key) == ("failed", "مقطع تالف")
    services.clear_deck_failure(key)
    assert services.deck_state(key) == ("pending", "")


def test_blocking_file_check_stops_the_write(period, monkeypatch):
    from apps.planning.domain.prep_checks import CheckResult

    monkeypatch.setattr(
        services, "check_pptx", lambda data, rebuilt: (CheckResult("S7", "fail", ("دقة المقطع 90",)),)
    )
    key = services.prepare_deck(GRADE10_SLUG, period.lesson, period.k)
    with pytest.raises(DeckError):
        services.build_period_deck_file(GRADE10_SLUG, period.lesson, period.k)
    state, detail = services.deck_state(key)
    assert state == "failed" and "S7" in detail
    assert not get_storage().exists(key)


def test_stored_clip_that_does_not_match_its_digest_is_refused(period):
    asset = Asset.objects.filter(lesson__code=period.lesson, number=period.examples[0].n).first()
    get_storage().put(asset.key, make_png(1600, 900, shade=255), "image/png")
    key = services.prepare_deck(GRADE10_SLUG, period.lesson, period.k)
    with pytest.raises(DeckError):
        services.build_period_deck_file(GRADE10_SLUG, period.lesson, period.k)
    assert "تجزئته" in services.deck_state(key)[1]


def test_periods_listing_marks_published_clips(period):
    rows = selectors.deck_periods(GRADE10_SLUG)
    assert len(rows) == 48
    row = next(r for r in rows if (r["lesson"], r["k"]) == (period.lesson, period.k))
    assert row["clips"] is True and row["examples"] == len(period.examples)
    others = [r for r in rows if r["lesson"] != period.lesson and r["examples"]]
    assert others and not any(r["clips"] for r in others)


def test_task_runs_in_place_and_returns_key(period):
    key = build_period_deck_task.delay(GRADE10_SLUG, period.lesson, period.k).get()
    assert services.deck_state(key) == ("ready", "")


# ───── الواجهة ─────
def test_api_requires_login(client):
    assert client.get(f"{API}/periods?course={GRADE10_SLUG}").status_code == 401


def test_api_outsider_is_forbidden(outsider_client):
    assert outsider_client.get(f"{API}/periods?course={GRADE10_SLUG}").status_code == 403


def test_api_request_status_download_flow(teacher_client, period):
    listing = teacher_client.get(f"{API}/periods?course={GRADE10_SLUG}").json()
    assert len(listing) == 48 and sum(r["clips"] for r in listing) >= 1
    body = {"course": GRADE10_SLUG, "lesson": period.lesson, "k": period.k}
    posted = teacher_client.post(f"{API}/", body, content_type="application/json")
    assert posted.status_code == 200 and posted.json()["status"] == "ready"
    name = f"{GRADE10_SLUG}-lesson-{period.lesson}-k{period.k}of{period.n}.pptx"
    assert posted.json()["filename"] == name
    query = f"course={GRADE10_SLUG}&lesson={period.lesson}&k={period.k}"
    assert teacher_client.get(f"{API}/status?{query}").json()["status"] == "ready"
    response = teacher_client.get(f"{API}/download?{query}")
    assert response.status_code == 200
    assert response["Content-Type"] == selectors.PPTX_CONTENT_TYPE
    assert f'filename="{name}"' in response["Content-Disposition"]
    assert len(_slides(response.content)) > 0


def test_api_errors(teacher_client, preps):
    item = next(p for p in preps if p.prep.examples)
    query = f"course={GRADE10_SLUG}&lesson={item.prep.lesson}&k={item.prep.k}"
    assert teacher_client.get(f"{API}/status?{query}").status_code == 422  # لا مقاطع منشورة
    assert teacher_client.get(f"{API}/status?course={GRADE10_SLUG}&lesson=9.9&k=1").status_code == 404
    assert teacher_client.get(f"{API}/periods?course=unknown").status_code == 404
    _publish(item.prep.lesson, item.prep.examples)
    assert teacher_client.get(f"{API}/download?{query}").status_code == 404  # قبل البناء
    bad = {"course": GRADE10_SLUG, "lesson": item.prep.lesson, "k": 0}
    assert teacher_client.post(f"{API}/", bad, content_type="application/json").status_code == 422
