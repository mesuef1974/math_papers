"""API مُنمَّط بـ Django Ninja. المصادقة: جلسة Django (كوكي HttpOnly) + CSRF."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest
from ninja import Field, NinjaAPI, Schema, Status
from ninja.errors import HttpError
from ninja.security import django_auth
from ninja.utils import check_csrf

from . import selectors, services

api = NinjaAPI(title="مولّد أوراق الرياضيات", version="1.0", docs_url="/docs/")


class MeOut(Schema):
    id: int
    username: str
    is_staff: bool
    admin_url: str = ""  # يظهر للطاقم فقط
    permissions: list[str]


class LoginIn(Schema):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=256)


class AuditOut(Schema):
    id: int
    action: str
    target: str
    created_at: str


class PingOut(Schema):
    ok: bool
    site: str


@api.get("/ping", response=PingOut)
def ping(request: HttpRequest):
    return {"ok": True, "site": settings.SITE_TITLE}


def me_payload(user) -> dict:
    return {
        "admin_url": f"/{settings.ADMIN_URL}" if user.is_staff else "",
        "id": user.pk,
        "username": user.get_username(),
        "is_staff": user.is_staff,
        "permissions": sorted(user.get_all_permissions()),
    }


@api.get("/me", response=MeOut, auth=django_auth)
def me(request: HttpRequest):
    return me_payload(request.user)


@api.post("/auth/login", response=MeOut)
def auth_login(request: HttpRequest, payload: LoginIn):
    # الدخول بلا مصادقة سابقة، فـ Ninja لا يفحص CSRF تلقائيًا هنا: نفحصه صراحة ضد login CSRF.
    if check_csrf(request) is not None:
        raise HttpError(403, "انتهت صلاحية الصفحة. أعد تحميلها.")
    try:
        user = services.sign_in(request, payload.username, payload.password)
    except services.LockedOutError as error:
        raise HttpError(429, "محاولات كثيرة. حاول بعد ساعة.") from error
    if user is None:
        raise HttpError(401, "اسم المستخدم أو كلمة المرور غير صحيحة")
    return me_payload(user)


@api.post("/auth/logout", response={204: None}, auth=django_auth)
def auth_logout(request: HttpRequest):
    services.sign_out(request)
    return Status(204, None)


@api.get("/audit", response=list[AuditOut], auth=django_auth)
def audit(request: HttpRequest, limit: int = 50):
    if not request.user.is_staff:
        raise HttpError(403, "للمشرفين فقط")
    services.record_audit(
        action="audit.view", actor=request.user, request_id=request.headers.get("X-Request-ID", "")
    )
    return [
        {"id": row.pk, "action": row.action, "target": row.target, "created_at": row.created_at.isoformat()}
        for row in selectors.recent_audit(min(limit, 200))
    ]
