"""API مُنمَّط بـ Django Ninja تحت /api/v1/. المصادقة: جلسة Django (كوكي HttpOnly) + CSRF.

مخطط الأخطاء موحد: {"detail": رسالة عربية} وقد يرافقه "errors" بتفاصيل حقول المدخلات.
"""

from __future__ import annotations

import hmac
from typing import Literal

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest
from ninja import Field, NinjaAPI, Query, Schema, Status
from ninja.errors import HttpError, ValidationError
from ninja.security import HttpBearer, django_auth
from ninja.utils import check_csrf

from . import selectors, services
from .middleware import request_id_of

api = NinjaAPI(
    title="مولّد أوراق الرياضيات",
    version="1",
    docs_url="/docs/",
    docs_decorator=staff_member_required,  # التوثيق ومخطط OpenAPI للطاقم فقط
)


@api.exception_handler(ValidationError)
def invalid_input(request: HttpRequest, exc: ValidationError):
    return api.create_response(
        request, {"detail": "مدخلات غير صالحة. راجع القيم وحاول مرة أخرى.", "errors": exc.errors}, status=422
    )


class MeOut(Schema):
    id: int
    username: str
    is_staff: bool
    is_superuser: bool
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
    subtitle: str


@api.get("/ping", response=PingOut)
def ping(request: HttpRequest):
    return {"ok": True, "site": settings.SITE_TITLE, "subtitle": settings.SITE_SUBTITLE}


def me_payload(user) -> dict:
    return {
        "admin_url": f"/{settings.ADMIN_URL}" if user.is_staff else "",
        "id": user.pk,
        "username": user.get_username(),
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
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
def audit(request: HttpRequest, limit: int = Query(50, ge=1, le=200)):
    if not request.user.is_staff:
        raise HttpError(403, "للمشرفين فقط")
    services.record_audit(action="audit.view", actor=request.user, request_id=request_id_of(request))
    return [
        {"id": row.pk, "action": row.action, "target": row.target, "created_at": row.created_at.isoformat()}
        for row in selectors.recent_audit(limit)
    ]


class BoardPushAuth(HttpBearer):
    """مفتاح سري ثابت لجهاز المالك وحده؛ المقارنة بزمن ثابت."""

    def authenticate(self, request: HttpRequest, token: str) -> bool | None:
        expected = settings.BOARD_PUSH_TOKEN
        return True if expected and hmac.compare_digest(token.encode(), expected.encode()) else None


class BoardRow(Schema):
    id: str = Field(max_length=40)
    title: str = Field("", max_length=300)
    group: Literal["running", "approval", "queued", "stuck", "done", "backlog"]
    at_stage: int = Field(ge=0, le=5)
    age: str = Field("", max_length=40)
    url: str = Field("", max_length=200, pattern=r"^(https://github\.com/.*)?$")
    note: str = Field("", max_length=300)


class BoardPulse(Schema):
    text: str = Field(max_length=500)
    warn: bool


class BoardIn(Schema):
    stages: list[str] = Field(max_length=10)
    cards: list[BoardRow] = Field(max_length=500)
    pulse: BoardPulse


class BoardOut(Schema):
    received_at: str | None
    board: BoardIn | None


@api.post("/automation/snapshot", response={204: None}, auth=BoardPushAuth())
def automation_push(request: HttpRequest, payload: BoardIn):
    services.store_board_snapshot(payload.dict())
    return Status(204, None)


@api.get("/automation/board", response=BoardOut, auth=django_auth)
def automation_board(request: HttpRequest):
    if not request.user.is_superuser:
        raise HttpError(403, "للمشرف العام فقط")
    row = selectors.board_snapshot()
    if row is None:
        return {"received_at": None, "board": None}
    return {"received_at": row.updated_at.isoformat(), "board": row.payload}
