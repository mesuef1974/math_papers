"""نشر الأصول: ملفات مجلد → طبقة التخزين + فهرس `Asset`. idempotent بتجزئة المحتوى.

المصدر مجلد مقاطع بأسماء `<درس>_m<مثال>_p<صفحة>[_cont].png`. المقطع بلا `_cont` هو الأصل (part=0)، وما يتبعه من تتمات
على صفحات تالية بترتيب الصفحة (part=1...). تشغيل ثانٍ على المجلد نفسه يعطي صفر تغييرات، وملف مفقود من التخزين يُعاد رفعه.
"""

from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

from django.core import signing
from django.db import transaction

from apps.core.services import record_audit
from apps.curriculum.models import Course, Lesson

from .models import Asset
from .storage import Storage, get_storage

CLIP = re.compile(r"^(?P<lesson>\d\.\d{1,2})_m(?P<n>\d{1,2})_p(?P<page>\d{1,3})(?P<cont>_cont)?\.png$")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
LINK_SALT = "assets.link"


class AssetError(ValueError):
    pass


@dataclass
class PublishReport:
    created: int = 0
    updated: int = 0
    repaired: int = 0  # الفهرس سليم والملف مفقود من التخزين فأُعيد رفعه
    unchanged: int = 0
    unmatched: list[str] = field(default_factory=list)  # ملفات PNG بأسماء لا تطابق النمط (لم تُنشر)
    orphans: int = 0  # أصول مفهرسة لم تعد في المصدر (تبقى)

    @property
    def changed(self) -> int:
        return self.created + self.updated + self.repaired

    @property
    def total(self) -> int:
        return self.changed + self.unchanged


def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != PNG_MAGIC or data[12:16] != b"IHDR":
        raise AssetError("الملف ليس PNG صالحًا")
    width, height = struct.unpack(">II", data[16:24])
    if not (0 < width <= 20000 and 0 < height <= 20000):
        raise AssetError(f"أبعاد غير معقولة: {width}x{height}")
    return width, height


@dataclass(frozen=True)
class Clip:
    path: Path
    lesson: str
    number: int
    part: int


def scan(source: Path) -> tuple[list[Clip], list[str]]:
    """يقرأ أسماء المجلد ويسند الأجزاء. يرفع AssetError عند غموض (مقطعان أصليان لمثال، أو تتمة بلا أصل)."""
    groups: dict[tuple[str, int], list[tuple[int, bool, Path]]] = {}
    unmatched = []
    for path in sorted(source.glob("*.png")):
        match = CLIP.match(path.name)
        if match is None:
            unmatched.append(path.name)
            continue
        key = (match["lesson"], int(match["n"]))
        groups.setdefault(key, []).append((int(match["page"]), bool(match["cont"]), path))
    clips, problems = [], []
    for (lesson, number), items in sorted(groups.items()):
        items.sort(key=lambda item: item[0])
        mains = [item for item in items if not item[1]]
        if len(mains) != 1 or items[0][1]:
            names = [item[2].name for item in items]
            problems.append(f"{lesson} مثال {number}: يلزم مقطع أصلي واحد في أول صفحاته ({names})")
            continue
        clips.extend(Clip(item[2], lesson, number, part) for part, item in enumerate(items))
    if problems:
        raise AssetError("؛ ".join(problems))
    return clips, unmatched


def asset_key(course: Course, clip: Clip, sha256: str) -> str:
    return f"assets/{course.slug}/{clip.lesson}/example{clip.number}-{clip.part}-{sha256[:16]}.png"


def publish_assets(course_slug: str, source: Path, storage: Storage | None = None) -> PublishReport:
    storage = storage or get_storage()
    course = Course.objects.filter(slug=course_slug).first()
    if course is None:
        raise AssetError(f"لا مقرر بالرمز {course_slug}: شغّل load_course أولًا")
    if not source.is_dir():
        raise AssetError(f"مجلد المصدر غير موجود: {source}")
    clips, unmatched = scan(source)
    lessons = {lesson.code: lesson for lesson in Lesson.objects.filter(course=course)}
    missing = sorted({c.lesson for c in clips} - set(lessons))
    if missing:
        raise AssetError(f"دروس غير موجودة في المقرر {course_slug}: {', '.join(missing)}")

    report = PublishReport(unmatched=unmatched)
    seen: set[int] = set()
    for clip in clips:
        data = clip.path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        width, height = png_size(data)
        key = asset_key(course, clip, sha)
        slot = {
            "course": course,
            "lesson": lessons[clip.lesson],
            "kind": Asset.Kind.EXAMPLE,
            "number": clip.number,
            "part": clip.part,
        }
        existing = Asset.objects.filter(**slot).first()
        if existing is not None:
            seen.add(existing.pk)
            if existing.sha256 == sha:
                if storage.exists(existing.key):
                    report.unchanged += 1
                else:
                    storage.put(existing.key, data, "image/png")
                    report.repaired += 1
                continue
        storage.put(
            key, data, "image/png"
        )  # الملف قبل الفهرس: فشل بينهما يترك ملفًا يتيمًا لا فهرسًا يشير إلى فراغ
        wanted = {"key": key, "sha256": sha, "size": len(data), "width": width, "height": height}
        old_key = ""
        with transaction.atomic():
            if existing is None:
                asset = Asset.objects.create(**slot, **wanted)
                report.created += 1
            else:
                old_key = existing.key
                for name, value in wanted.items():
                    setattr(existing, name, value)
                existing.save()
                asset = existing
                report.updated += 1
        seen.add(asset.pk)
        if old_key and old_key != key:
            storage.delete(old_key)
    report.orphans = Asset.objects.filter(course=course).exclude(pk__in=seen).count()
    if report.changed:
        record_audit(
            action="assets.publish",
            target=course_slug,
            payload={
                "created": report.created,
                "updated": report.updated,
                "repaired": report.repaired,
                "unchanged": report.unchanged,
            },
        )
    return report


def link_token(asset: Asset) -> str:
    """رمز موقّع قصير العمر (الحد عند القراءة) يحمل معرّف الأصل وبصمة تجزئته، فتبطله إعادة نشر المقطع."""
    return signing.TimestampSigner(salt=LINK_SALT).sign(f"{asset.pk}:{asset.sha256[:16]}")


def asset_for_token(token: str, max_age: int) -> Asset:
    try:
        value = signing.TimestampSigner(salt=LINK_SALT).unsign(token, max_age=max_age)
        pk, fingerprint = value.split(":")
        asset = Asset.objects.get(pk=int(pk))
    except (signing.BadSignature, ValueError, Asset.DoesNotExist) as error:
        raise AssetError("رابط غير صالح أو منتهي") from error
    if asset.sha256[:16] != fingerprint:
        raise AssetError("رابط قديم: المقطع نُشر من جديد")
    return asset
