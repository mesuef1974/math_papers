"""طبقة الخدمات: كل عملية كتابة تمرّ من هنا، idempotent حيث أمكن، وتسجّل في AuditLog."""

from __future__ import annotations

from typing import Any

from axes.exceptions import AxesBackendPermissionDenied
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.http import HttpRequest

from .middleware import request_id_of
from .models import AuditLog


@transaction.atomic
def record_audit(
    *,
    action: str,
    actor: AbstractBaseUser | None = None,
    target: str = "",
    payload: dict[str, Any] | None = None,
    request_id: str = "",
) -> AuditLog:
    """idempotent على (action, target, request_id) عندما يُمرَّر request_id."""
    if request_id:
        existing = AuditLog.objects.filter(action=action, target=target, request_id=request_id).first()
        if existing:
            return existing
    return AuditLog.objects.create(
        action=action,
        actor=actor if getattr(actor, "pk", None) else None,
        target=target,
        payload=payload or {},
        request_id=request_id,
    )


class LockedOutError(PermissionError):
    """محاولات فاشلة كثيرة: django-axes يقفل الحساب مؤقتًا."""


def sign_in(request: HttpRequest, username: str, password: str) -> AbstractBaseUser | None:
    """يصادق ويبدّل مفتاح الجلسة (ضد تثبيت الجلسة)، ويسجّل النجاح والفشل في سجل التدقيق.

    معرّف الطلب من الخادم لا من العميل، وإلا ثبّته مهاجم ليُسجَّل فشل واحد بدل محاولاته كلها.
    """
    request_id = request_id_of(request)
    try:
        user = authenticate(request, username=username, password=password)
    except AxesBackendPermissionDenied as error:
        record_audit(action="auth.locked", target=username[:255], request_id=request_id)
        raise LockedOutError(username) from error
    if user is None:
        record_audit(action="auth.failed", target=username[:255], request_id=request_id)
        return None
    login(request, user)
    record_audit(action="auth.login", actor=user, target=username[:255], request_id=request_id)
    return user


def sign_out(request: HttpRequest) -> None:
    user = request.user
    if user.is_authenticated:
        record_audit(action="auth.logout", actor=user, target=user.get_username())
    logout(request)
