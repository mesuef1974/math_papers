"""Celery: ما يتجاوز 300 مللي ثانية يذهب إلى مهمة هنا (قاعدة المشروع). المهام idempotent دائمًا.

المهام في `apps/<app>/tasks.py` وتُكتشف تلقائيًا. العامل خدمة ثانية (`scripts/railway-worker.sh`)، والوسيط Redis من
`REDIS_URL`؛ بلا `REDIS_URL` تُنفَّذ المهمة في مكانها فورًا (انظر `CELERY_TASK_ALWAYS_EAGER` في الإعدادات).
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("math_papers")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
