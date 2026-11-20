---
paths:
  - "config/celery.py"
  - "apps/**/tasks.py"
  - "scripts/railway-worker.sh"
  - "apps/papers/pdf.py"
---
# المهام الخلفية

- المهام الخلفية Celery (`config/celery.py`): المهام في `apps/<app>/tasks.py` وتُكتب idempotent (الإقرار بعد الإتمام، فموت العامل يعيدها). الوسيط Redis من `REDIS_URL`، وبلا `REDIS_URL` (تطوير واختبار) تُنفَّذ في مكانها فورًا. العامل خدمة ثانية على Railway أمر بدئها `bash scripts/railway-worker.sh`، وفحصها `python manage.py worker_ping`. لا تُستدعى مهمة من مسار الويب في الإنتاج قبل قيام خدمة العامل. توليد PDF ما زال بخيط داخل خادم الويب (`apps/papers/pdf.py`) حتى يوجد تخزين ملفات مشترك (المرحلة 3 من خطة المناهج).
