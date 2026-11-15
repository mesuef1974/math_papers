# خط استخراج أدلة المعلم

شيفرة فقط. نصوص الأدلة وصور صفحاتها ومقاطعها في مجلد الكتاب خارج المستودع (`out` في `book.yaml`)، ولا يدخل المستودع نص دليل.

## التشغيل

```bash
python -m tools.extraction <مجلد الكتاب> validate     # فحص book.yaml
python -m tools.extraction <مجلد الكتاب> ocr          # تصيير وPaddleOCR (بيئة guide_extract)
python -m tools.extraction <مجلد الكتاب> all          # layout ثم images وobjectives وexamples وchecks
```

المراحل منفردة: `layout`، `images`، `objectives`، `examples`، `checks`. كل مرحلة idempotent وتطبع ملخصها العددي.
الاختبارات: `python -m pytest tools/extraction` (اختبارات الصور تحتاج numpy وPillow وpymupdf وتُتجاوَز دونها).

## book.yaml

المفاتيح المطلوبة: `id`، `title`، `language`، `pages`، `out`، `pdf` (`dir`، `pattern`، `prefer_suffix`)، `dirs` (`ocr`، `render`)،
`markers` (`opener`، `objective_label`، `objective_intro`، `objective_end`)، `standards.pattern`، `layout` (`anchor`، `end`، `image_min`).
العلامات تُوحَّد بـ `text.norm` وتُطابَق بلا فراغ. الاختيارية:

- `layout.anchor`: `opener` (الدرس يُعرف بافتتاحيته) أو `analysis` (بجدول تحليل التمارين `markers.analysis`).
- `layout.end`: `next_opener` (ينتهي قبل الافتتاحية التالية أو أول `markers.end_stop`) أو `quiz` (صفحة `markers.quiz`).
- `layout.opener_needs_standard`، `layout.standard_on` (`opener` أو `quiz`)، `layout.id_pattern`، `unit_gap`، `min_span`، `max_span`.
- `objectives`: `column` (`right`، `left`، `all`)، `gap`، `check` (كشف علامات الأهداف الملونة بالصورة).
- `examples`: `max`، `jump`، `pattern`، `numbering: sequence` (حين لا يقرأ OCR أرقام الشارات)، و`dirs.vision` و`dirs.badges` مصدران اختياريان.
- `exercises`: `max`، `jump`. `outputs.generic_<اسم>` يوجّه مخرجًا إلى ملف آخر حين تشترك أدوات قديمة في الاسم.

## المصدر والحالة

كل حقل مستخرج غلاف `{value, source, status}`: المصدر `guide` أو `derived` أو `library` أو `teacher`، والحالة `ok` أو `review` أو `missing`
(`fields.py`). الحدود والصفحات `derived`؛ نص الهدف `guide` ومستوى بلوم `derived` من `bloom_lexicon_ar.json`، والفعل خارج المعجم
`unclassified` ولا يُخمَّن. المثال `ok` إن شهد له مصدران مستقلان أو شارة مقتصّة، وإلا `review`.

## المدقّقات (`checks.py`)

مجموع التمارين المدّعى مقابل سلسلة أرقام OCR مستقلة عنه (فرق واحد مقبول أو تطابق «دليل المهام»)، وأسئلة اختبار الدرس مقابل أعماقها
(أرقام متصلة من 1، عمق 1 إلى 3، ورموز الصفوف هي رموز الصفحة). المدقّق بلا بيانات يعيد `None` ولا يُحسب نجاحًا.
