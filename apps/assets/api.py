"""تقديم الأصول للمعلمين المسجّلين. لا رابط عام: الجلسة (401 دونها) أو رابط موقّع قصير العمر يصدره معلم مسجَّل.

- GET /assets/                 فهرس مقاطع مقرر (بيانات فقط)
- GET /assets/{id}/link        رابط موقّع (يُسجَّل في AuditLog)
- GET /assets/{id}/file        الملف بالجلسة
- GET /assets/blob/{token}     الملف بالرابط الموقّع (للوسوم <img> والعروض)
"""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from ninja.throttling import AnonRateThrottle, UserRateThrottle

from apps.core.middleware import request_id_of
from apps.core.services import record_audit
from apps.papers.access import TeacherAuth

from . import selectors, services
from .models import Asset
from .storage import StorageError

router = Router(tags=["الأصول"], auth=TeacherAuth(), throttle=[UserRateThrottle()])


class AssetOut(Schema):
    id: int
    course: str
    lesson: str
    kind: str
    number: int
    part: int
    width: int
    height: int
    sha256: str

    @staticmethod
    def resolve_course(obj: Asset) -> str:
        return obj.course.slug

    @staticmethod
    def resolve_lesson(obj: Asset) -> str:
        return obj.lesson.code


class AssetFilter(Schema):
    course: str
    lesson: str = ""


class LinkOut(Schema):
    url: str
    expires_in: int


def _asset(asset_id: int) -> Asset:
    asset = Asset.objects.select_related("course", "lesson").filter(pk=asset_id).first()
    if asset is None:
        raise HttpError(404, "المقطع غير موجود")
    return asset


def _image(asset: Asset) -> HttpResponse:
    try:
        data = selectors.asset_bytes(asset)
    except StorageError as error:
        raise HttpError(404, "ملف المقطع غير متاح في التخزين") from error
    response = HttpResponse(data, content_type=asset.content_type)
    response["Cache-Control"] = f"private, max-age={settings.ASSET_LINK_TTL}"
    response["ETag"] = f'"{asset.sha256[:16]}"'
    response["Content-Disposition"] = "inline"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("assets/", response=list[AssetOut])
def list_assets(request: HttpRequest, filters: Query[AssetFilter]):
    return list(selectors.list_assets(filters.course, filters.lesson))


@router.get("assets/{int:asset_id}/link", response=LinkOut)
def link(request: HttpRequest, asset_id: int):
    asset = _asset(asset_id)
    record_audit(
        action="assets.link",
        actor=request.user,
        target=str(asset.pk),
        payload={"course": asset.course.slug, "lesson": asset.lesson.code},
        request_id=request_id_of(request),
    )
    token = services.link_token(asset)
    return {"url": f"/api/v1/assets/blob/{token}", "expires_in": settings.ASSET_LINK_TTL}


@router.get("assets/{int:asset_id}/file")
def file(request: HttpRequest, asset_id: int):
    asset = _asset(asset_id)
    record_audit(
        action="assets.file",
        actor=request.user,
        target=str(asset.pk),
        request_id=request_id_of(request),
    )
    return _image(asset)


@router.get("assets/blob/{token}", auth=None, throttle=[AnonRateThrottle("300/m")])
def blob(request: HttpRequest, token: str):
    try:
        asset = services.asset_for_token(token, settings.ASSET_LINK_TTL)
    except services.AssetError as error:
        raise HttpError(403, str(error)) from error
    return _image(asset)
