# قواعد استعمال علامة «مولّد أوراق الرياضيات»

المفهوم المعتمد: a1 «ألف الأوراق». الفكرة بجملة: تتصل الألف المهموزة بالورقة الأمامية ذات السطور الثلاثة، وتتّسع خلفها ورقتان نحو اليسار بقواعد منحنية تحفظ هيئة السكتش 11.

## الصيغ
- `math_papers-mark.svg` الرمز بالألوان: للترويسة والواجهة على الورق الفاتح.
- `math_papers-mark-mono.svg` أحادي أسود: للطباعة بلون واحد والختم.
- `math_papers-mark-reversed.svg` أبيض على داكن: للوضع الداكن والخلفيات الداكنة.
- `math_papers-wordmark.svg` الكلمة «أوراق» مسارات بلا نص حي.
- `math_papers-lockup.svg` الرمز والكلمة معًا (الرمز على اليمين في RTL).
- `favicon.svg`، `favicon.ico` (16/32/48)، `favicon-32.png`، `apple-touch-icon.png`، `icon-192.png`، `icon-512.png`، `maskable-512.png`، `site.webmanifest`.
- `tokens.css` متغيرات الألوان، `BrandMark.vue` مكوّن Vue 3 للرمز، و`BrandLockup.vue` للقفل (إن وُجد قفل).

## المساحة الخالية والحد الأدنى
- اترك حول الرمز مساحة لا تقل عن ربع عرضه من كل جهة.
- الحد الأدنى للرمز وحده 160 بكسل على الشاشة و6 مم في الطباعة؛ للقفل مع الكلمة 160 بكسل ارتفاعًا.
- الأيقونات دون هذا الحد (favicon وapple-touch-icon وما صغر عنه) مولّدة للتوافق فقط: حدّ السماكة لا يتحقق فيها، بعلم المالك عند الاعتماد.
- لا تدوير، لا تمديد، لا ظل، لا تدرج، لا حدود مضافة، لا تغيير نسب الرمز إلى الكلمة.

## الألوان
| الدور | القيمة | التباين على الورق #FBF3E4 |
|---|---|---|
| لون العلامة | #8E2433 | 7.77:1 |
| الحبر | #2A1D1A | 14.77:1 |
| التمييز | #DB943C | 2.29:1 |
| نص أبيض على لون العلامة | #FFFFFF | 8.57:1 |

## إعلان العناصر الزخرفية والمعلوماتية (WCAG 1.4.11)
- الرمز كاملًا عنصر معلوماتي: يجب أن يبقى تباينه مع خلفيته 3:1 على الأقل (محقَّق أعلاه).
- عناصر التمييز (data-tone="accent") زخرفية: العلامة تُعرف بدونها، فهي معفاة من شرط التباين.

## الربط في المشروع
1. انسخ `favicon.svg` و`favicon.ico` وملفات PNG و`site.webmanifest` إلى `public/`.
2. أدرج `tokens.css` في `styles/index.css` قبل باقي الأنماط، واستعمل `--color-mark-*` فقط.
3. استبدل `components/BrandMark.vue` و`components/BrandLockup.vue` بالمولَّدَين (لا تعدّل الملفات القديمة في مكانها: هذا إصدار جديد).
4. في `<head>`: `<link rel="icon" href="/favicon.svg" type="image/svg+xml">`، و`<link rel="icon" href="/favicon.ico" sizes="any">`، و`<link rel="apple-touch-icon" href="/apple-touch-icon.png">`، و`<link rel="manifest" href="/site.webmanifest">`.

## الفحص الآلي عند الاعتماد
- أصغر سماكة عند 160 بكسل: 1.68 (الحد 1.5).
- تغطية صغير/256: 1.029؛ مكوّنات عند الحجم الصغير: 5.
- نقاط الارتكاز: 89؛ الأشكال: 6.
- أقرب مراجع إدراكيًا (للعلم؛ ليست تصريحًا قانونيًا): solidjs (14/64)، uikit (14/64)، immer (15/64)
- فحص العلامة التجارية رسميًا (وزارة التجارة والصناعة/WIPO) مسؤولية المالك قبل أي نشر تجاري.

## الملفات
- BrandLockup.vue
- BrandMark.vue
- apple-touch-icon.png
- audit.json
- concept.json
- favicon-32.png
- favicon.ico
- favicon.svg
- icon-192.png
- icon-512.png
- maskable-512.png
- math_papers-lockup-mono.svg
- math_papers-lockup.svg
- math_papers-mark-mono.svg
- math_papers-mark-reversed.svg
- math_papers-mark-white.svg
- math_papers-mark.svg
- math_papers-wordmark.svg
- site.webmanifest
- tokens.css
- USAGE.md
