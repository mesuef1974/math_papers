"""طبقة الخدمات: كل عملية كتابة تمرّ من هنا، idempotent حيث أمكن، وتسجّل في AuditLog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from axes.exceptions import AxesBackendPermissionDenied
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.http import HttpRequest

from .middleware import request_id_of
from .models import AuditLog
from .selectors import plan_metrics

PLAN_FILE = "docs/innovation_plan.yaml"


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


class PlanMetricsError(ValueError):
    """ملف الخطة غائب أو لا يصلح للقياس."""


def plan_kpi_keys(plan: dict[str, Any]) -> list[str]:
    return [kpi["key"] for initiative in plan.get("initiatives", []) for kpi in initiative.get("kpis", [])]


def write_plan_metrics(root: Path, plan_file: str = PLAN_FILE) -> Path:
    """يكتب مؤشرات الخطة JSON في `metrics_file`. idempotent: بلا تاريخ ولا ترتيب متغيّر، فقاعدة لم تتغير
    تعطي الملف نفسه بايتًا ببايت. الملف أعداد ونسب مجمَّعة فقط."""
    import yaml  # في بيئة التطوير وحدها (requirements-dev): الأمر يُشغَّل من جهاز المالك لا من الخادم

    plan_path = root / plan_file
    if not plan_path.is_file():
        raise PlanMetricsError(f"ملف الخطة غير موجود: {plan_path}")
    try:
        plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
        keys = plan_kpi_keys(plan)
        target = (root / plan["metrics_file"]).resolve()
    except (yaml.YAMLError, KeyError, TypeError, AttributeError) as error:
        raise PlanMetricsError(f"ملف الخطة غير سليم: {error!r}") from error
    if not target.is_relative_to(root.resolve()):
        raise PlanMetricsError(f"metrics_file خارج المستودع: {plan['metrics_file']}")
    text = json.dumps(plan_metrics(keys), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    return target


def sign_out(request: HttpRequest) -> None:
    user = request.user
    if user.is_authenticated:
        record_audit(action="auth.logout", actor=user, target=user.get_username())
    logout(request)
