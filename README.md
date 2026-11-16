# مولّد أوراق الرياضيات

Django 5 + Django Ninja + Vue 3 (Vite/Pinia/TS) + PostgreSQL + Redis، على Railway، مع أتمتة التطوير مدمجة.

## التشغيل محليًا

```bash
cp .env.example .env
docker compose up -d db redis
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
cd frontend && npm install && cd ..
python manage.py migrate && python manage.py createsuperuser
```

ثم في طرفيتين: `python manage.py runserver` و`npm --prefix frontend run dev`. افتح http://127.0.0.1:8000 (Django يحقن حزم Vite مع HMR).
وثائق API: http://127.0.0.1:8000/api/docs/

صورة الإنتاج تثبّت من `requirements.lock` (إصدارات وتجزئات sha256، `--require-hashes`)، فلا يدخل النشرَ إصدار جديد إلا بتجديد القفل. عند تغيير `requirements.txt`، أو لترقية الاعتماديات، جدّده وراجع فرقه:

```bash
uv pip compile requirements.txt --generate-hashes --python-version 3.12 --python-platform linux --no-header -o requirements.lock
```

`tests/test_requirements_lock.py` يفشل إن خالف القفل `requirements.txt` أو نقصته تجزئة.

## النشر على Railway

1. مشروع جديد → أضف PostgreSQL وRedis.
2. خدمة من هذا المستودع. الإعداد الفعلي من لوحة الخدمة (Settings → Deploy) لا من `railway.toml`: الخدمات الجديدة لا تقرأ Config as Code
   (مهمل، وينتهي دعمه للقائم في 2026-12-01)، وقد بقي حقل Pre-deploy فارغًا فلم تُطبَّق هجرات #54 و#59 تلقائيًا (طُبّقت يدويًا 2026-11-16).
   اضبط في خدمة الويب: Pre-deploy Command = `bash scripts/railway-predeploy.sh`، وPre-deploy Timeout = 300 (الافتراضي 5 يُفشل `migrate`)،
   وHealthcheck Path = `/health/`، وRestart On Failure بخمس محاولات، وأبقِ Start Command فارغًا (أمر الصورة `CMD` هو `railway-release.sh`).
   خدمة العامل تُضبط من اللوحة أيضًا بلا Pre-deploy. اللوحة لا يحرسها المستودع، فحارس `migrate --check` في `scripts/railway-release.sh` يُفشل بدء
   نسخة على قاعدة لم تُهاجَر فيبقى النشر السابق حيًّا. `railway.toml` مرجع للقيم المقصودة لا مصدر الإعداد.
3. المتغيرات: `SECRET_KEY`، `ALLOWED_HOSTS`، `CSRF_TRUSTED_ORIGINS`، و`DATABASE_URL=${{Postgres.DATABASE_URL}}`، `REDIS_URL=${{Redis.REDIS_URL}}`.
4. PDF الخادمي: Chromium يأتي من بطاقة Dockerfile (فرع `card/pdf-chromium`)؛ بدونه يرد المسار 503 والطباعة من المتصفح تبقى.
   يحتاج `REDIS_URL` (حالة المهمة مشتركة بين عمّال gunicorn) و`localhost` في `ALLOWED_HOSTS` (كما يحتاجه فحص الصحة)؛
   `PDF_RENDER_BASE_URL` اختياري إن لم يكن الخادم على `http://localhost:$PORT`.
## الأتمتة

انظر `automation/README.md`. الخلاصة: بطاقة في الدفتر → المشغّل ينشئ worktree ويشغّل النموذج بصلاحيات مخفَّضة → فحص محلي →
PR → CI → اعتماد مربوط بالـ SHA → merge queue (نافذة النشر) → Railway.

في GitHub فعّل: Branch protection على `main` مع Require merge queue، والفحوص المطلوبة: `بوابة الجودة`، `سطر الاعتماد يطابق الرأس`.

## الفحص قبل الدفع

```bash
python scripts/prepush_check.py --frontend
```
