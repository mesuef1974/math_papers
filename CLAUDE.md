# مولّد أوراق الرياضيات

Django 5 + Django Ninja (API تحت `/api/`) + Vue 3 (Vite، Pinia، TypeScript) تُحقن عبر django-vite في `templates/spa.html`.
PostgreSQL + Redis. النشر على Railway (`railway.toml`).

## البنية
- `config/` إعدادات (base/development/production/testing)، `apps/<app>/` كل تطبيق: `models.py` نحيل، `services.py` كتابة،
  `selectors.py` قراءة، `api.py` مسارات Ninja، `tests/`.
- `frontend/src/`: `pages/` (lazy)، `components/`، `stores/` (Pinia)، `api/client.ts` (جلسة + CSRF، لا توكنات في localStorage).
- `scripts/` بوابات، `automation/` دفتر البطاقات والمشغّل، `security/sensitive_paths.json` المسارات الحسّاسة.
- `tools/extraction/` خط استخراج أدلة المعلم (شيفرة واختبارات فقط؛ النصوص والمقاطع خارج المستودع بإعداد `book.yaml` لكل كتاب): انظر `README.md` فيه.

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
- توزيع الدرجات في المفتاح مشتق لا مخزَّن: `apps/papers/domain/marking.py` يوزّع درجة الفرع المقالي على خطواته ثم بند «الجواب النهائي» (أصغر وحدة نصف درجة، والخطوات الزائدة تُدمج)، والموضوعي درجته لرمز الإجابة. `PartOut` يعيد حسابه دائمًا فلا يُقبل من العميل، ويعرضه `AnswerKey.vue` و`key_pages` في Word بالصفوف نفسها.
- فهرس العاشر `apps/knowledge/data/grade10_index.json` مشتق عددي فقط (معايير وممارسات ومستويات بلوم وتمثيلات الأمثلة وصفوف تحليل التمارين و«دليل المهام» وأعماق الاختبار وعدد المصطلحات)، بلا نص دليل: مخطط `domain/grade10_index.py` صارم لا يملك حقلًا نصيًا حرًّا، ويُبنى بـ `python manage.py build_grade10_index --source <مجلد الكتاب خارج المستودع>` ويقرؤه `selectors.grade10_index()`.
- الاختبارات بلا Postgres محلي: `DATABASE_URL=sqlite:///test.db python -m pytest --create-db`.

## الدخول والصلاحيات
- كل مسارات `apps/papers/api.py` خلف `TeacherAuth`: جلسة (401 دونها) وصلاحية `curriculum.generate_paper` (403 دونها).
- المعلم = عضو مجموعة `teachers`: `python manage.py create_teacher <اسم>` (idempotent). المشرف العام يملك الصلاحية ضمنًا.
- الدخول `POST /api/auth/login` يفحص CSRF صراحة ويبدّل الجلسة ويُسجَّل في AuditLog؛ axes يقفل بعد 5 محاولات.
- `TRUSTED_PROXY_COUNT` (الإنتاج 1 لـ Railway) يحدد عنوان العميل الحقيقي للقفل؛ لا تجعله صفرًا خلف وكيل.

## الهوية البصرية
- هوية «أوراق» v7 من أداة سِمة (المفهوم a1 «ألف الأوراق»؛ مرجعها `brand/math_papers/` وقواعد استعمالها في `USAGE.md` فيه): عنابي #8E2433 للفعل الأساسي، وذهبي #DB943C للتزيين فقط، وخط Cairo مضمَّن محليًا (OFL) بوزن 800 للعناوين، وزوايا بنصف قطر 8px (للبطاقات 16px، وللبطاقة الكبيرة في الجوال 24px، ولوحة الرمز 32px كما في `--r` بـ `screens/*.html`)، وأيقونات خط 1.75 في `assets/icons` عبر `AppIcon.vue`. الرمز `BrandMark.vue` بلون واحد `--color-mark-ink`: عنابي نهارًا وأبيض ليلًا. الشعار المقفل `BrandLockup.vue` هو الرمز مع كلمة «أوراق» مسارات، والكلمة بلون `--color-ink`. `--color-mark-accent` (#DB943C) معرَّف للهوية ولا يستعمله مكوّن. أيقونات التطبيق (`favicon.svg` و`favicon.ico` وصور PNG) و`site.webmanifest` في `frontend/public/` بعنابي ثابت، وروابطها و`theme-color` في `templates/spa.html`.
- ملفات الهوية مولَّدة من سِمة ولا تُعدَّل يدويًا: الرمز والشعار المقفل والأيقونات ومتغيرات `--color-mark-*`؛ أي تغيير فيها إصدار جديد من سِمة. يتبعها في المشروع شيئان يُحدَّثان مع كل إصدار: شعار Word `apps/papers/word/assets/lockup.png` (تحويل نقطي لـ `brand/math_papers/math_papers-lockup.svg` بلا تغيير في الرسم)، و`BRAND` في `apps/papers/word/ooxml.py` (يساوي `--color-brand` في `print.css`).
- تذييل الورق واحد في الطباعة وPDF وWord: الشعار المقفل يمينًا، وسطران: عنوان الورقة الجاري بسطر واحد ثم «© سفيان مسيف» ورمز جوال و55296286 (`utils/brand.ts` و`COPYRIGHT_*` في `word/builder.py`)، والترقيم يسارًا. Chromium لا يرسم الصور في هوامش `@page` ولا يثبّت tfoot في صفحته الأخيرة، فالإطار `PrintFrame.vue` (حول `PaperSet` و`PaperBundle`) جدول بـ tfoot مخفي يحجز 9mm في كل صفحة، وعنصر `.print-foot` ثابت يرسم الشريط فيه (`print.css`)؛ على الشاشة يُجرَّد الجدول ولا يظهر. الشعار فيه خلفية من `assets/brand/lockup.svg` (نسخة طبق الأصل يحرسها `PrintFooter.test.ts` وتُحدَّث مع كل إصدار من سِمة)، وأيقونة الجوال `word/assets/phone.png` بخط 1.75 بلون العلامة.
- السمة: نهارية، وليلية تلقائيًا بتفضيل النظام أو يدويًا من مبدّل الترويسة (`ThemeToggle.vue`، مخزن `stores/theme.ts`). التفضيل وحده في localStorage (ليس سرًّا)، ويُطبَّق قبل أول رسم بـ `public/theme-init.js` (ملف خارجي لأن CSP تمنع النص المضمّن). الليلي لواجهة الشاشة فقط؛ الورقة، معروضةً على الشاشة أو مطبوعةً (PDF وWord)، بألوان الهوية النهارية دائمًا: العنابي للعناوين والشارات وترويسات الجداول والخطوط الرئيسة، والذهبي للتزيين، والنص والرسوم بحبر داكن.
- خط الورقة واحد في الطباعة وPDF وWord: Noto Naskh Arabic (OFL، البناء الكامل بالعربي واللاتيني)، مضمَّن في `frontend/src/assets/fonts` (`--font-print`) وداخل ملف Word نفسه (`apps/papers/word/assets/fonts`، و`embed_fonts` في `ooxml.py`). نصوص الرسوم بخط KaTeX المضمَّن (`--font-math`). لا يدخل الورقة خط من جهاز المعلم ولا من الخادم، و`utils/printFonts.ts` يحمّل الخطوط قبل الطباعة. ارتفاع السطر في Word (`LINE_MULTIPLE` في `ooxml.py`) يساوي `--leading-body` في `print.css`.
- الأنماط مركزية في `frontend/src/styles/` عبر `index.css`: `tokens.css` (المصدر الوحيد للألوان والخطوط والمسافات؛ كتلتا الوضع الليلي متطابقتان)، `fonts.css`، `base.css`، `layout.css`، `components.css` (`.btn`، `.field`، `.input`، `.panel`، `.alert`، `.badge-k/a/r`، `.segmented`، `.icon`)، `print.css` (نطاق الورقة `.sheet`: يثبّت المتغيرات على ألوان الهوية النهارية وخط الورق ومقاس الصفحة، على الشاشة والورق؛ ألوان Word في `apps/papers/word/ooxml.py`).
- المكونات تستعمل الأصناف المشتركة والمتغيرات فقط؛ لا لون خام ولا متغير غير معرّف (يفرضه `styles/designTokens.test.ts`)، والتباين بين كل نص وخلفيته 4.5:1 فأكثر، والحدود والتركيز 3:1، في الوضعين (يفرضه `styles/contrast.test.ts`). أي لون جديد يُضاف في الكتلتين ويُضاف زوجه إلى الاختبار.
- المعاينة المطابقة: الورقة على الشاشة بقواعد الورق نفسها (عرض A4 بهوامش `@page` من متغيرات `--page-*`، وخط الورق وحجمه وارتفاع سطره)، وتُصغَّر كلها حين تضيق الحاوية (`--paper-zoom` من `composables/usePaperFit.ts`) ولا يُعاد تدفقها. مكوّنات الورقة (`PaperSheet` و`PaperQuestion` و`PaperPart` و`AnswerKey` وما تحتها) بلا استعلامات عرض شاشة، وقواعد `@media print` فيها للفواصل بين الصفحات فقط، وما يظهر على الشاشة وحدها (زر الاستبدال) خارج مجرى المحتوى في هامش الصفحة (يفرض ذلك `styles/print.test.ts`). حدود الصفحات الحقيقية في تبويب «صفحات PDF» (`PdfPreview.vue`): ملف الخادم نفسه في إطار من الأصل نفسه، يُطلب عند فتح التبويب وتُعلَّم المعاينة قديمةً بتغيّر الورقة أو إعدادات الطباعة مع زر تحديث؛ والورقة تبقى في الصفحة خلفه (`.behind-pdf` للشاشة وحدها) فتطبعها «طباعة أو حفظ PDF». التضمين مسموح لـ `GET /api/v1/pdf/<id>/file?inline=1` وحده (`X-Frame-Options: SAMEORIGIN` و`frame-ancestors 'self'`)، وكل رد آخر (التنزيل وWord والواجهة البرمجية) يبقى `DENY` و`'none'`. المتصفح الذي لا يعرض PDF داخل الصفحة (`navigator.pdfViewerEnabled`) يرى رابط فتح الملف. التقليب في عرضين بمكوّن واحد `PageFlipper.vue` (السابقة والتالية ورقم الصفحة ومفاتيح الأسهم: الأيسر تالية، الأيمن سابقة): «الورقة صفحة بصفحة» (الافتراضي، `PagedSheet.vue`: بطاقة A4 نافذتها مقطع من الورقة المتصلة تُزاح بـ `translateY` وتنتهي عند حدود العناصر المحسوبة في `utils/paging.ts`؛ الحدود تقديرية لا فواصل الطباعة الحقيقية، وأول جزء في السؤال ليس حدًّا، والطباعة تعيد الورقة متصلة بـ `@media print`)، و«صفحات PDF» (الخادم يُرجع `pages` في حالة المهمة، و`count_pages` في `pdf.py` يعدّ كائنات `/Type /Page`؛ الصفحة تُرسم على canvas بـ pdf.js في `PdfPageView.vue` و`utils/pdfPages.ts` بدل عارض المتصفح الذي كان يُعاد بناؤه مع كل صفحة فيومض: دقة اللوحة عرض الحاوية × `devicePixelRatio` (سقف 3000 بكسل)، والصفحة كاملة بنسبتها في ارتفاع النافذة، ومخزن لثلاث صفحات (الحالية وجارتاها) تُحمَّل الجارتان مسبقًا، والتقليب ينسخ الصفحة الجاهزة فوق القديمة دفعة واحدة فلا لوحة فارغة بين صفحتين؛ المكتبة وعاملها يُحمَّلان كسولًا من الأصل نفسه فتناسب CSP). دون عدد صفحات يبقى عارض المتصفح بلا أزرار، وبلا عارض داخلي رابط الفتح. «الورقة متصلة» العرض الطويل القديم. الحارس البصري `python scripts/visual_guard.py` (يدويًا قبل أي تغيير في أنماط الورقة؛ لا في pytest ولا CI): Chromium حقيقي بلا نافذة يقيس عرض وارتفاع كل `.question` و`.part` للاختبار الكامل والقصير وورقة العمل على الشاشة بحجم A4 الحقيقي وفي وسائط الطباعة بعرض محتوى الصفحة، ويفشل عند فرق أكثر من بكسل أو اختلاف العدد، ويتحقق من ملف PDF المضمَّن؛ مقارنته `compare_boxes` مختبرة في `tests/test_visual_guard.py`.
- بيان التبنّي (`brand/math_papers/identity/ADOPTION.yaml`، مولَّد من سِمة): ظهور الرمز بالحركة `styles/motion.css` (نسخة طبق الأصل من `identity/motion.css`) بالصنف `sima-mark-intro` عبر `utils/markIntro.ts` مرة عند أول عرض في شاشة الافتتاح `SplashScreen.vue` (تظهر بعد 150ms من تأخر فحص الجلسة)، وقالب الشرائح 16:9 `SlideFrame.vue` (تخطيطا العنوان والمحتوى بأحجام نسبة إلى عرض الإطار)، و`styles/adoptionParity.test.ts` يقرأ `token_map` من ADOPTION.yaml ويطابقه مع `tokens.css` نهارًا وليلًا ويتحقق من تطابق نسختي `motion.css`. تُحدَّث النسختان مع كل إصدار من سِمة.
- النمط (`patterns/motif-soft.svg`) مكوّن `BrandPattern.vue` بلونين من متغيرات السمة (`--color-brand-soft` و`--color-sand-soft`): شريط أسفل شاشة الافتتاح، وفوق رسالة الحالة الفارغة (`EmptyState.vue`)، وعلى حافة غلاف الكراسة العليا (`BookletCover.vue`، مضمَّن في الصفحة فيُطبع في PDF)، وفي غلاف Word صورة `apps/papers/word/assets/pattern_band.png` (تحويل نقطي 300dpi بعرض المحتوى، تُحدَّث مع كل إصدار من سِمة كالشعار). زخرفة فقط: لا نص فوقه ولا يجاور الشعار.
- لوحة الإدارة (`admin.css` و`templates/admin/_lockup.html`): الترويسة بسطح الورقة وخط سفلي وقفل الهوية الحالي، وخلفية مسطّحة بلا شبكة. `_lockup.html` نسخة من `BrandLockup.vue` يحرسها `styles/adminIdentity.test.ts`، وتُحدَّث مع كل إصدار من سِمة.
- المدى الرقمي في نص عربي (السنوات) يُعرض عبر `isolateNumberRanges` من `utils/bidi.ts`.

## أوامر
```bash
python manage.py runserver            # 8000
npm --prefix frontend run dev          # 5173 (HMR عبر django-vite)
python scripts/prepush_check.py --frontend
python automation/ledger.py list
```
