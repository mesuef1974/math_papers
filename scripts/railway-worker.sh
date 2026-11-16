#!/bin/bash
# أمر بدء خدمة العامل (Celery) على Railway: خدمة ثانية من المستودع والصورة نفسيهما، بلا healthcheck HTTP
# وبلا preDeploy (الهجرات تشغّلها خدمة الويب وحدها). فحصها: python manage.py worker_ping.
set -euo pipefail

[ -n "${REDIS_URL:-}" ] || { echo "::error:: REDIS_URL مطلوب للعامل" >&2; exit 1; }
[ -n "${DATABASE_URL:-}" ] || { echo "::error:: DATABASE_URL مطلوب للعامل" >&2; exit 1; }
export DJANGO_SETTINGS_MODULE=config.settings.production

# قوالب تُصيَّر داخل العامل (صفحة الطباعة مثلًا) تحتاج manifest الثابت في قرص حاويتها هي.
python manage.py collectstatic --noinput --clear
exec celery -A config worker \
  --loglevel="${CELERY_LOG_LEVEL:-info}" \
  --concurrency="${CELERY_WORKER_CONCURRENCY:-2}" \
  --max-tasks-per-child="${CELERY_WORKER_MAX_TASKS_PER_CHILD:-100}"
