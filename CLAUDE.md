# مولّد أوراق الرياضيات

Django 5 + Django Ninja (API تحت `/api/`) + Vue 3 (Vite، Pinia، TypeScript) تُحقن عبر django-vite في `templates/spa.html`.
PostgreSQL + Redis. النشر على Railway (`railway.toml`).

## البنية
- `config/` إعدادات (base/development/production/testing)، `apps/<app>/` كل تطبيق: `models.py` نحيل، `services.py` كتابة،
  `selectors.py` قراءة، `api.py` مسارات Ninja، `tests/`.
- `frontend/src/`: `pages/` (lazy)، `components/`، `stores/` (Pinia)، `api/client.ts` (جلسة + CSRF، لا توكنات في localStorage).
- المهام الخلفية Celery في `apps/<app>/tasks.py` وتُكتب idempotent؛ التفصيل (الوسيط والعامل على Railway وPDF) في `.claude/rules/background-jobs.md`.
- `scripts/` بوابات، `automation/` دفتر البطاقات والمشغّل ومزامنة الدفتر مع GitHub (`sync.py`)، `security/sensitive_paths.json` المسارات الحسّاسة.
- `tools/extraction/` خط استخراج أدلة المعلم (شيفرة واختبارات فقط؛ النصوص والمقاطع خارج المستودع بإعداد `book.yaml` لكل كتاب): انظر `README.md` فيه.

## قواعد
- DDD + Clean Architecture + SOLID. ORM فقط. Skinny Models / Fat Services. idempotent. > 300ms → مهمة خلفية.
- RTL-first بخصائص منطقية. Lazy loading. لا `**`/`###` مبالَغ في الوثائق.
- أمن: جلسات HttpOnly+Secure+SameSite، RBAC، Audit Trail (`apps.core.models.AuditLog`)، لا أسرار في الشيفرة.
- كل تغيير نماذج يرافقه `makemigrations`؛ هجرات expand/contract لا هدم.
- قبل أي دفع: `python scripts/prepush_check.py`.

## ما لا تفعله
- لا `git push` ولا `gh pr merge` ولا `railway` من الجلسة؛ المشغّل والبوابات يفعلان ذلك. الحارس `.claude/hooks/guard_git.py` يحجب كل `git push` (القاعدة `push-any`، عدا `--dry-run`) إلا بإذن المالك الصريح مكتوبًا في `GUARD_GIT_ALLOW='<الإذن وتاريخه>'`، و`.claude/settings.json` يحجب `gh pr merge` و`railway` في Bash وPowerShell (`tests/test_guard_git.py`).
- الدمج بعد اعتماد المالك وحده: حين يقول «اعتمد N» وتخضرّ الفحوص يُكتب سطر الاعتماد، ثم `python scripts/merge_gate.py N --repo <المستودع> --enable` يفعّل الدمج التلقائي وGitHub يدمج. ما ترفضه البوابة (مسارات محظورة، فحص فاشل) يبقى دمجًا يدويًا للمالك، ولا التفاف عليها.
- لا تعديل على `.github/`، `scripts/*gate*`, `security/`, lockfiles, `Dockerfile`, `railway.toml` داخل بطاقة عادية. الحرّاس أنفسهم (`merge_gate.ALWAYS_FORBIDDEN`: ومنها `.claude/hooks/` و`automation/*.py` وسكربتات الفحص) لا يدفعها المشغّل ولا تُدمج آليًا.

## نطاق المحتوى
- المسائل تُولَّد أصليًا في `apps/papers/domain/generators.py`، ولا يدخل هنا نص من كتاب Savvas أو من الاختبارات أو الخطة الفصلية.
- كل مولّد جديد يحتاج نوع فحص عددي مستقل في `apps/papers/tests/test_generators.py`.
- تفصيل المولّدات ومصدر الجزء وأرقام الكتاب والمقررات وجداول المواصفات والفهرس المشتق ومقاطع العروض في `.claude/rules/content-scope.md` (يُحمَّل عند لمس `apps/papers` و`knowledge` و`curriculum` و`planning` و`assets` و`tools/extraction`).
- خطة توحيد المناهج (المقرر والمحمِّل الواحد والأصول وخط الاستخراج) بمراحلها وشروط انتهائها: `docs/curriculum_platform_plan.md`.
- الاختبارات بلا Postgres محلي: `DATABASE_URL=sqlite:///test.db python -m pytest --create-db`.

## الدخول والصلاحيات
- كل مسارات `apps/papers/api.py` خلف `TeacherAuth`: جلسة (401 دونها) وصلاحية `curriculum.generate_paper` (403 دونها).
- المعلم = عضو مجموعة `teachers`: `python manage.py create_teacher <اسم>` (idempotent). المشرف العام يملك الصلاحية ضمنًا.
- الدخول `POST /api/auth/login` يفحص CSRF صراحة ويبدّل الجلسة ويُسجَّل في AuditLog؛ axes يقفل بعد 5 محاولات.
- بيانات الطالب الفردية (قرار المالك 2026-11-25) في `planning.SectionStudent` و`ItemResult` وحدهما: رقم قيد واسم أول واسم عائلة، ونوع الخطأ يُشتق من بنك البنود لا من العميل. `/api/v1/results/<مقرر>/<درس>` للمعلم في شعبه فقط (403 لغيرها)، وسجل التدقيق أعداد بلا أسماء ولا أرقام قيد. الاحتفاظ حتى نهاية العام: `python manage.py purge_student_results` (idempotent، `--dry-run`).
- `TRUSTED_PROXY_COUNT` (الإنتاج 1 لـ Railway) يحدد عنوان العميل الحقيقي للقفل؛ لا تجعله صفرًا خلف وكيل.

## الهوية البصرية
- هوية «أوراق» من أداة سِمة: ملفاتها المولَّدة لا تُعدَّل يدويًا. الألوان والخطوط من `frontend/src/styles/tokens.css` وحده، والتباين 4.5:1 للنص و3:1 للحدود في الوضعين (`designTokens.test.ts` و`contrast.test.ts`).
- الورقة بألوان الهوية النهارية وخطها في الشاشة والطباعة وPDF وWord. التفصيل (التذييل والسمة والخطوط والمعاينة المطابقة والتقليب والحارس البصري وقالب المدرسة) في `.claude/rules/brand-ui.md` (يُحمَّل عند لمس `frontend` و`brand` و`templates` و`apps/papers/word`).

## أوامر
```bash
python manage.py runserver            # 8000
npm --prefix frontend run dev          # 5173 (HMR عبر django-vite)
python scripts/prepush_check.py --frontend
python automation/ledger.py list
```
