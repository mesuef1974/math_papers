#!/bin/bash
# startCommand: لكل نسخة في حاويتها. collectstatic هنا لأن STATIC_ROOT قرص محلي للحاوية،
# وحاوية preDeploy حاوية عابرة منفصلة — ما يُجمَّع هناك لا يصل هنا (درس حادثة 2026-09-17).
set -euo pipefail

# حارس الهجرات: الهجرة عمل preDeploy وحده (scripts/railway-predeploy.sh). إن لم يُنفَّذ (إعداد الخدمة في
# اللوحة لا يقرأ railway.toml مثلًا) فلا تبدأ نسخة على مخطط قديم: migrate --check قراءة فقط، يطبع الهجرات
# غير المطبّقة ويخرج بغير الصفر، فيفشل البدء وفحص الصحة ويبقى النشر السابق حيًّا. لا هجرة هنا (سباق DDL).
if ! python manage.py migrate --check --plan; then
  echo "::error:: هجرات غير مطبّقة أو القاعدة غير متاحة: هل نُفِّذ preDeploy؟ لن تبدأ هذه النسخة." >&2
  exit 1
fi

python manage.py collectstatic --noinput --clear
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout 60 \
  --access-logfile - --error-logfile -
