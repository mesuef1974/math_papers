"""صلاحية التوليد (RBAC): مجموعة المعلمين تحمل صلاحية curriculum.generate_paper، والمشرف العام يملكها ضمنًا."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import AbstractBaseUser, Group, Permission
from django.db import transaction
from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.security import SessionAuth

from apps.core.services import record_audit

GENERATE_PERMISSION = "curriculum.generate_paper"
TEACHER_GROUP = "teachers"


def can_generate(user: Any) -> bool:
    return bool(user.is_authenticated and user.has_perm(GENERATE_PERMISSION))


class TeacherAuth(SessionAuth):
    """جلسة Django صالحة (401 دونها) مع صلاحية التوليد (403 دونها)."""

    def authenticate(self, request: HttpRequest, key: str | None) -> Any:
        user = super().authenticate(request, key)
        if user is None:
            return None
        if not can_generate(user):
            raise HttpError(403, "حسابك لا يملك صلاحية توليد الأوراق")
        return user


@transaction.atomic
def teacher_group() -> Group:
    group, _ = Group.objects.get_or_create(name=TEACHER_GROUP)
    app_label, codename = GENERATE_PERMISSION.split(".")
    group.permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return group


@transaction.atomic
def ensure_teacher(username: str, password: str | None = None) -> tuple[AbstractBaseUser, bool]:
    """idempotent: ينشئ المعلم إن لم يوجد (بكلمة مرور تجتاز المدقّقات)، ويضمّه إلى مجموعة المعلمين."""
    user_model = get_user_model()
    user = user_model.objects.filter(username=username).first()
    created = user is None
    if created:
        if not password:
            raise ValueError("كلمة المرور مطلوبة لمعلم جديد")
        user = user_model(username=username)
        password_validation.validate_password(password, user)
        user.set_password(password)
        user.save()
    user.groups.add(teacher_group())
    record_audit(action="teacher.grant", target=username, payload={"created": created})
    return user, created
