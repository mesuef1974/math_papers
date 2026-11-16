"""فحص عامل المهام الخلفية من طرف إلى طرف: مهمة تُرسل إلى الطابور ويُنتظر ردّ العامل.

    python manage.py worker_ping [--timeout 10]
الخروج 0 حين يردّ العامل، وخطأ حين لا يردّ في المهلة أو يتعذّر الوصول إلى الوسيط.
"""

from __future__ import annotations

from celery.exceptions import TimeoutError as CeleryTimeoutError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from kombu.exceptions import OperationalError

from apps.core.tasks import ping


class Command(BaseCommand):
    help = "يرسل مهمة فحص إلى طابور Celery وينتظر ردّ العامل."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=float, default=10.0, help="مهلة انتظار الرد بالثواني")

    def handle(self, *args, **options):
        if settings.CELERY_TASK_ALWAYS_EAGER:
            ping.delay().get()
            self.stdout.write("تنفيذ فوري (بلا REDIS_URL): المهمة نُفّذت في مكانها، ولا عامل يُفحص.")
            return
        timeout = options["timeout"]
        try:
            reply = ping.delay().get(timeout=timeout)
        except CeleryTimeoutError as exc:
            raise CommandError(f"لا ردّ من العامل خلال {timeout:g} ثانية: هل خدمة العامل تعمل؟") from exc
        except OperationalError as exc:
            raise CommandError(f"تعذّر الوصول إلى الوسيط: {exc}") from exc
        self.stdout.write(f"العامل يعمل: {reply}")
