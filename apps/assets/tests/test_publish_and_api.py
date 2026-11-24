"""نشر الأصول (idempotent بالتجزئة) وتقديمها خلف الجلسة وبروابط موقّعة."""

import pytest
from django.core.management import CommandError, call_command

from apps.assets.models import Asset
from apps.assets.services import AssetError, asset_for_token, link_token, publish_assets, scan
from apps.assets.storage import LocalStorage, get_storage
from apps.assets.tests.conftest import make_png
from apps.core.models import AuditLog
from apps.curriculum.courses import GRADE10_SLUG
from apps.knowledge.services import load_course

pytestmark = pytest.mark.django_db


@pytest.fixture
def g10(db):
    load_course(GRADE10_SLUG)


def write(folder, name, shade=0):
    (folder / name).write_bytes(make_png(shade=shade))


@pytest.fixture
def clips(tmp_path, g10):
    folder = tmp_path / "clips"
    folder.mkdir()
    write(folder, "1.1_m1_p28.png", 1)
    write(folder, "1.1_m2_p29.png", 2)
    write(folder, "1.2_m3_p39.png", 3)
    write(folder, "1.2_m3_p40_cont.png", 4)
    write(folder, "2.10_m1_p189.png", 5)
    (folder / "index.json").write_text("{}")  # غير PNG: يُتجاهل
    return folder


def test_scan_assigns_parts_by_page_and_ignores_non_png(clips):
    found, unmatched = scan(clips)
    assert [(c.lesson, c.number, c.part) for c in found] == [
        ("1.1", 1, 0),
        ("1.1", 2, 0),
        ("1.2", 3, 0),
        ("1.2", 3, 1),
        ("2.10", 1, 0),
    ]
    assert unmatched == []


def test_publish_creates_then_second_run_changes_nothing(clips):
    first = publish_assets(GRADE10_SLUG, clips)
    assert (first.created, first.updated, first.unchanged, first.total) == (5, 0, 0, 5)
    assets = list(Asset.objects.order_by("id"))
    assert {a.course.slug for a in assets} == {GRADE10_SLUG}
    assert all((a.width, a.height, a.content_type) == (4, 3, "image/png") for a in assets)
    assert all(get_storage().exists(a.key) for a in assets)
    second = publish_assets(GRADE10_SLUG, clips)
    assert (second.changed, second.unchanged) == (0, 5)
    assert Asset.objects.count() == 5
    assert AuditLog.objects.filter(action="assets.publish").count() == 1  # الثاني بلا تغيير فلا تدقيق


def test_publish_repairs_a_missing_blob_and_updates_a_changed_clip(clips):
    publish_assets(GRADE10_SLUG, clips)
    store = get_storage()
    victim = Asset.objects.get(lesson__code="1.1", number=1)
    store.delete(victim.key)
    changed = Asset.objects.get(lesson__code="1.1", number=2)
    old_key = changed.key
    write(clips, "1.1_m2_p29.png", 99)

    report = publish_assets(GRADE10_SLUG, clips)
    assert (report.repaired, report.updated, report.unchanged, report.created) == (1, 1, 3, 0)
    assert store.exists(victim.key)
    changed.refresh_from_db()
    assert changed.key != old_key and store.exists(changed.key) and not store.exists(old_key)


def test_orphans_are_counted_but_kept(clips):
    publish_assets(GRADE10_SLUG, clips)
    (clips / "2.10_m1_p189.png").unlink()
    report = publish_assets(GRADE10_SLUG, clips)
    assert report.orphans == 1 and report.unchanged == 4
    assert Asset.objects.count() == 5


def test_unmatched_png_is_reported_not_published(clips):
    write(clips, "random.png")
    report = publish_assets(GRADE10_SLUG, clips)
    assert report.unmatched == ["random.png"] and report.created == 5


def test_publish_rejects_bad_sources(clips, tmp_path):
    with pytest.raises(AssetError, match="لا مقرر"):
        publish_assets("nope", clips)
    with pytest.raises(AssetError, match="غير موجود"):
        publish_assets(GRADE10_SLUG, tmp_path / "missing")
    write(clips, "9.9_m1_p1.png")
    with pytest.raises(AssetError, match="غير موجودة"):
        publish_assets(GRADE10_SLUG, clips)
    (clips / "9.9_m1_p1.png").unlink()
    write(clips, "1.1_m3_p31_cont.png")  # تتمة بلا مقطع أصلي
    with pytest.raises(AssetError, match="مقطع أصلي"):
        publish_assets(GRADE10_SLUG, clips)
    (clips / "1.1_m3_p31_cont.png").unlink()
    write(clips, "1.1_m1_p30.png")  # أصليان لمثال واحد
    with pytest.raises(AssetError, match="مقطع أصلي"):
        publish_assets(GRADE10_SLUG, clips)
    assert Asset.objects.count() == 0  # الفحص قبل أي رفع


def test_publish_rejects_a_fake_png(clips):
    (clips / "1.1_m1_p28.png").write_bytes(b"not a png at all, just text bytes")
    with pytest.raises(AssetError, match="PNG"):
        publish_assets(GRADE10_SLUG, clips)


def test_command_reports_counts_and_errors(clips, capsys):
    call_command("publish_assets", GRADE10_SLUG, "--source", str(clips))
    call_command("publish_assets", GRADE10_SLUG, "--source", str(clips))
    out = capsys.readouterr().out
    assert "جديد 5" in out and "بلا تغيير 5" in out
    with pytest.raises(CommandError, match="لا مقرر"):
        call_command("publish_assets", "nope", "--source", str(clips))


# --- التقديم ---


@pytest.fixture
def published(clips):
    publish_assets(GRADE10_SLUG, clips)
    return Asset.objects.get(lesson__code="1.1", number=1)


def test_every_route_needs_a_session(client, published):
    for url in (
        f"/api/v1/assets/?course={GRADE10_SLUG}",
        f"/api/v1/assets/{published.pk}/link",
        f"/api/v1/assets/{published.pk}/file",
    ):
        assert client.get(url).status_code == 401, url


def test_a_logged_in_non_teacher_gets_403(outsider_client, published):
    assert outsider_client.get(f"/api/v1/assets/{published.pk}/file").status_code == 403
    assert outsider_client.get(f"/api/v1/assets/?course={GRADE10_SLUG}").status_code == 403


def test_teacher_lists_assets_without_keys(teacher_client, published):
    rows = teacher_client.get(f"/api/v1/assets/?course={GRADE10_SLUG}&lesson=1.2").json()
    assert [(r["lesson"], r["number"], r["part"]) for r in rows] == [("1.2", 3, 0), ("1.2", 3, 1)]
    assert set(rows[0]) == {"id", "course", "lesson", "kind", "number", "part", "width", "height", "sha256"}


def test_teacher_reads_file_with_session_and_it_is_audited(teacher_client, published):
    res = teacher_client.get(f"/api/v1/assets/{published.pk}/file")
    assert res.status_code == 200 and res["Content-Type"] == "image/png"
    assert res.content == make_png(shade=1)
    assert res["Cache-Control"].startswith("private") and res["X-Content-Type-Options"] == "nosniff"
    log = AuditLog.objects.get(action="assets.file")
    assert log.actor.username == "teacher" and log.target == str(published.pk)
    assert teacher_client.get("/api/v1/assets/999999/file").status_code == 404


def test_signed_link_serves_without_a_session_and_is_audited(teacher_client, client, published):
    link = teacher_client.get(f"/api/v1/assets/{published.pk}/link").json()
    assert link["url"].startswith("/api/v1/assets/blob/") and link["expires_in"] == 300
    assert AuditLog.objects.get(action="assets.link").actor.username == "teacher"
    anonymous = type(client)()  # عميل بلا جلسة
    res = anonymous.get(link["url"])
    assert res.status_code == 200 and res.content == make_png(shade=1)


def test_tampered_expired_and_stale_links_are_refused(teacher_client, published, settings, clips):
    token = link_token(published)
    assert teacher_client.get(f"/api/v1/assets/blob/{token}x").status_code == 403
    assert teacher_client.get("/api/v1/assets/blob/garbage").status_code == 403
    with pytest.raises(AssetError):
        asset_for_token(token, max_age=-1)  # منتهٍ
    settings.ASSET_LINK_TTL = -1
    assert teacher_client.get(f"/api/v1/assets/blob/{token}").status_code == 403
    settings.ASSET_LINK_TTL = 300
    assert teacher_client.get(f"/api/v1/assets/blob/{token}").status_code == 200
    write(clips, "1.1_m1_p28.png", 77)
    publish_assets(GRADE10_SLUG, clips)  # إعادة نشر المقطع تبطل الرابط القديم
    assert teacher_client.get(f"/api/v1/assets/blob/{token}").status_code == 403


def test_missing_blob_is_404_not_500(teacher_client, published):
    get_storage().delete(published.key)
    assert teacher_client.get(f"/api/v1/assets/{published.pk}/file").status_code == 404


def test_storage_is_a_local_storage_in_tests(local_store):
    assert isinstance(get_storage(), LocalStorage) and get_storage().root == local_store.resolve()


def test_practice_clips_publish_as_their_own_kind_beside_the_example_of_the_same_number(tmp_path, g10):
    """`<درس>_t<مثال>_p<صفحة>` مقطع «حاول أن تحل» (نوع practice) بجانب مقطع المثال نفسه دون تعارض، وidempotent."""
    folder = tmp_path / "clips"
    folder.mkdir()
    write(folder, "1.2_m3_p39.png", 3)
    write(folder, "1.2_t3_p40.png", 6)
    write(folder, "1.2_t3_p41_cont.png", 7)
    found, unmatched = scan(folder)
    assert [(c.number, c.part, c.kind) for c in found] == [
        (3, 0, Asset.Kind.EXAMPLE),
        (3, 0, Asset.Kind.PRACTICE),
        (3, 1, Asset.Kind.PRACTICE),
    ]
    assert unmatched == []
    first = publish_assets(GRADE10_SLUG, folder)
    assert (first.created, first.unchanged) == (3, 0)
    rows = list(Asset.objects.order_by("kind", "part").values_list("kind", "number", "part", "key"))
    assert [r[:3] for r in rows] == [("example", 3, 0), ("practice", 3, 0), ("practice", 3, 1)]
    assert "/example3-0-" in rows[0][3] and "/practice3-0-" in rows[1][3] and "/practice3-1-" in rows[2][3]
    assert publish_assets(GRADE10_SLUG, folder).changed == 0


def test_practice_clip_without_its_own_original_is_rejected(tmp_path):
    folder = tmp_path / "clips"
    folder.mkdir()
    write(folder, "1.2_t3_p41_cont.png", 7)
    with pytest.raises(AssetError, match="تدريب 3"):
        scan(folder)
