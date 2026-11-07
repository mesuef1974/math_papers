"""إنشاء معلم أو منح حساب قائم صلاحية التوليد. idempotent: إعادة التشغيل لا تكرر شيئًا."""

from __future__ import annotations

import getpass

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.papers.access import ensure_teacher


class Command(BaseCommand):
    help = "ينشئ حساب معلم بصلاحية توليد الأوراق، أو يمنحها لحساب قائم."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username: str, **options):
        password = None
        if not get_user_model().objects.filter(username=username).exists():
            password = getpass.getpass("كلمة المرور: ")
            if password != getpass.getpass("أعدها: "):
                raise CommandError("كلمتا المرور غير متطابقتين")
        try:
            _, created = ensure_teacher(username, password)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error
        self.stdout.write(self.style.SUCCESS(f"{'أُنشئ' if created else 'مُنح'} المعلم {username}"))
