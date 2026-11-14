# مولّد أوراق الرياضيات

Django 5 + Django Ninja (API تحت `/api/`) + Vue 3 (Vite، Pinia، TypeScript) تُحقن عبر django-vite في `templates/spa.html`.
PostgreSQL + Redis. النشر على Railway (`railway.toml`).

## البنية
- `config/` إعدادات (base/development/production/testing)، `apps/<app>/` كل تطبيق: `models.py` نحيل، `services.py` كتابة،
  `selectors.py` قراءة، `api.py` مسارات Ninja، `tests/`.
- `frontend/src/`: `pages/` (lazy)، `components/`، `stores/` (Pinia)، `api/client.ts` (جلسة + CSRF، لا توكنات في localStorage).
- `scripts/` بوابات، `automation/` دفتر البطاقات والمشغّل، `security/sensitive_paths.json` المسارات الحسّاسة.

## قواعد
- DDD + Clean Architecture + SOLID. ORM فقط. Skinny Models / Fat Services. idempotent. > 300ms → مهمة خلفية.
- RTL-first بخصائص منطقية. Lazy loading. لا `**`/`###` مبالَغ في الوثائق.
- أمن: جلسات HttpOnly+Secure+SameSite، RBAC، Audit Trail (`apps.core.models.AuditLog`)، لا أسرار في الشيفرة.
- كل تغيير نماذج يرافقه `makemigrations`؛ هجرات expand/contract لا هدم.
- قبل أي دفع: `python scripts/prepush_check.py`.

## ما لا تفعله
- لا `git push` ولا `gh pr merge` ولا `railway` من الجلسة؛ المشغّل والبوابات يفعلان ذلك (`.claude/hooks/guard_git.py` يحجب).
- الدمج بعد اعتماد المالك وحده: حين يقول «اعتمد N» وتخضرّ الفحوص يُكتب سطر الاعتماد، ثم `python scripts/merge_gate.py N --repo <المستودع> --enable` يفعّل الدمج التلقائي وGitHub يدمج. ما ترفضه البوابة (مسارات محظورة، فحص فاشل) يبقى دمجًا يدويًا للمالك، ولا التفاف عليها.
- لا تعديل على `.github/`، `scripts/*gate*`, `security/`, lockfiles, `Dockerfile`, `railway.toml` داخل بطاقة عادية.

## نطاق المحتوى
- المسائل تُولَّد أصليًا في `apps/papers/domain/generators.py`، ولا يدخل هنا نص من كتاب Savvas أو من الاختبارات أو الخطة الفصلية.
- كل مولّد جديد يحتاج نوع فحص عددي مستقل في `apps/papers/tests/test_generators.py`.
- الاختبارات بلا Postgres محلي: `DATABASE_URL=sqlite:///test.db python -m pytest --create-db`.

## الدخول والصلاحيات
- كل مسارات `apps/papers/api.py` خلف `TeacherAuth`: جلسة (401 دونها) وصلاحية `curriculum.generate_paper` (403 دونها).
- المعلم = عضو مجموعة `teachers`: `python manage.py create_teacher <اسم>` (idempotent). المشرف العام يملك الصلاحية ضمنًا.
- الدخول `POST /api/auth/login` يفحص CSRF صراحة ويبدّل الجلسة ويُسجَّل في AuditLog؛ axes يقفل بعد 5 محاولات.
- `TRUSTED_PROXY_COUNT` (الإنتاج 1 لـ Railway) يحدد عنوان العميل الحقيقي للقفل؛ لا تجعله صفرًا خلف وكيل.

## الهوية البصرية
- هوية «أوراق» v6 من أداة سِمة (المفهوم a1 «ألف الأوراق»؛ مرجعها `brand/math_papers/` وقواعد استعمالها في `USAGE.md` فيه): عنابي #8E2433 للفعل الأساسي، وذهبي #E3AB3C للتزيين فقط، وخط Cairo مضمَّن محليًا (OFL) بوزن 800 للعناوين، وزوايا حادة 2px، وأيقونات خط 1.75 في `assets/icons` عبر `AppIcon.vue`. الرمز `BrandMark.vue` بلون واحد `--color-mark-ink`: عنابي نهارًا وأبيض ليلًا. الشعار المقفل `BrandLockup.vue` هو الرمز مع كلمة «أوراق» مسارات، والكلمة بلون `--color-ink`. `--color-mark-accent` (#DB943C) معرَّف للهوية ولا يستعمله مكوّن. أيقونات التطبيق (`favicon.svg` و`favicon.ico` وصور PNG) و`site.webmanifest` في `frontend/public/` بعنابي ثابت، وروابطها و`theme-color` في `templates/spa.html`.
- ملفات الهوية مولَّدة من سِمة ولا تُعدَّل يدويًا: الرمز والشعار المقفل والأيقونات ومتغيرات `--color-mark-*`؛ أي تغيير فيها إصدار جديد من سِمة. يتبعها في المشروع شيئان يُحدَّثان مع كل إصدار: شعار Word `apps/papers/word/assets/lockup.png` (تحويل نقطي لـ `brand/math_papers/math_papers-lockup.svg` بلا تغيير في الرسم)، و`BRAND` في `apps/papers/word/ooxml.py` (يساوي `--color-brand` في `print.css`).
- السمة: نهارية، وليلية تلقائيًا بتفضيل النظام أو يدويًا من مبدّل الترويسة (`ThemeToggle.vue`، مخزن `stores/theme.ts`). التفضيل وحده في localStorage (ليس سرًّا)، ويُطبَّق قبل أول رسم بـ `public/theme-init.js` (ملف خارجي لأن CSP تمنع النص المضمّن). الليلي على الشاشة فقط؛ الورق المطبوع (PDF وWord) بألوان الهوية النهارية دائمًا: العنابي للعناوين والشارات وترويسات الجداول والخطوط الرئيسة، والذهبي للتزيين، والنص والرسوم بحبر داكن.
- خط الورقة واحد في الطباعة وPDF وWord: Noto Naskh Arabic (OFL، البناء الكامل بالعربي واللاتيني)، مضمَّن في `frontend/src/assets/fonts` (`--font-print`) وداخل ملف Word نفسه (`apps/papers/word/assets/fonts`، و`embed_fonts` في `ooxml.py`). نصوص الرسوم بخط KaTeX المضمَّن (`--font-math`). لا يدخل الورقة خط من جهاز المعلم ولا من الخادم، و`utils/printFonts.ts` يحمّل الخطوط قبل الطباعة. ارتفاع السطر في Word (`LINE_MULTIPLE` في `ooxml.py`) يساوي `--leading-body` في `print.css`.
- الأنماط مركزية في `frontend/src/styles/` عبر `index.css`: `tokens.css` (المصدر الوحيد للألوان والخطوط والمسافات؛ كتلتا الوضع الليلي متطابقتان)، `fonts.css`، `base.css`، `layout.css`، `components.css` (`.btn`، `.field`، `.input`، `.panel`، `.alert`، `.badge-k/a/r`، `.segmented`، `.icon`)، `print.css` (يثبّت المتغيرات على ألوان الهوية النهارية للورق؛ ألوان Word في `apps/papers/word/ooxml.py`).
- المكونات تستعمل الأصناف المشتركة والمتغيرات فقط؛ لا لون خام ولا متغير غير معرّف (يفرضه `styles/designTokens.test.ts`)، والتباين بين كل نص وخلفيته 4.5:1 فأكثر، والحدود والتركيز 3:1، في الوضعين (يفرضه `styles/contrast.test.ts`). أي لون جديد يُضاف في الكتلتين ويُضاف زوجه إلى الاختبار.
- المدى الرقمي في نص عربي (السنوات) يُعرض عبر `isolateNumberRanges` من `utils/bidi.ts`.

## أوامر
```bash
python manage.py runserver            # 8000
npm --prefix frontend run dev          # 5173 (HMR عبر django-vite)
python scripts/prepush_check.py --frontend
python automation/ledger.py list
```
