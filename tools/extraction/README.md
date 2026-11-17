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

## جدول تحليل التمارين (`tables.py`)

مرحلة `tables` (قبل `layout` في `all` حين `layout.anchor: analysis` ويوجد `dirs.tables`): تقرأ صناديق OCR لصفحة فيها `tables.title`
(الافتراضي «تحليل التمارين») وتحدد الأعمدة من ترويستها، والمثال المدموج رأسيًا من خطوط الجدول الأفقية في صورة الصفحة، وتكتب
`dirs.tables/NNNN.json` (`rows` و`task_guide`) ثم `tables.json` ملخصًا. لا تحذف ملف صفحة قديمًا. الاختياري في `tables`: `title`،
`headers` (نص الترويسة إلى `example`/`exercises`/`dok`/`standard`)، `task_levels`، `header_window`، `row_gap`، `dark`، `dark_fraction`.

## دمج المصادر (`fusion.py`)

مرحلة `fusion` (بعد `layout`): لكل درس يدمج أرقام التمارين والأمثلة ورموز الممارسات من OCR والرؤية (`dirs.vision` اختياري) وجدول
التحليل (`dirs.tables`) في `fusion.json`: ثقة كل رقم `both`/`ocr`/`vision`/`filled`، وما رُفض لخروجه عن سلسلة 1..max (`exercises.max/jump`
و`examples.max/jump`) وصفحات المراجعة. الاختياري: `practices` (`marker` و`names`) و`fusion` (`degenerate` و`name_tail` و`exercise_pattern`).
المرحلة التي تعتمد `layout` تبنيه قبل حساب ختمها فلا يبطل الختم عند أول تشغيل.

## سجل الدرس والمفردات والانحدار (`lesson.py`، `vocabulary.py`، `regression.py`)

مرحلة `lesson` (آخر `all`): تجمع لكل درس `lessons/lesson_X_Y.json` (`dirs.lessons`، افتراضًا `lessons` في مجلد الكتاب) من layout وobjectives
والدمج والجدول ورؤية الأمثلة والمفردات، ثم `lessons.json` ملخصًا. كل حقل غلاف `{value, source, status}`. الإعداد `lesson`:
`example_vision` (مفاتيح `dirs` بترتيب الأولوية؛ أول مجلد فيه ملف الصفحة يغلب)، `overrides` (ملف في `dirs.gold` يصحّح تمثيلات مثال بسببه)،
`representation_note`، `schema_version`، `library_fields`، `pending_fields`. المفردات من `dirs.vocab/NNNN.json` (review وnew وflat) مدموجة بنص OCR
ومصحَّحة هجاءً بـ `dirs.gold/lesson_*.json`؛ تشغيل الرؤية نفسه خارج الخط. الانحدار على الذهبي (`regression_vs_gold` و`regression_soft`)
يُكتب في السجل إن وُجد `dirs.gold`، ولا يدخل الحقول.

## تمثيلات الأمثلة بالرؤية (`reps.py`)

سلسلة تمريرات تُحسِّن قائمة تمثيلات كل مثال (جدول/بياني/جبري/سياق حياتي) بأسئلة نعم/لا على مقطعه المصغّر (`dirs.crops/<صفحة>_<ك>_thumb.png`)،
كل تمريرة تقرأ مجلد رؤية (`src`) وتكتب آخر (`dst`) فلا يُمَسّ السابق، ثم تتمة «تابع المثال n» من أعلى صفحة الطالب التالية. الرؤية نفسها مُحقَنة
(`ask(صورة، سؤال، مخطط) -> dict`) فلا يلزم المنطق نموذجًا في الاختبار. الإعداد `reps`: `questions` (تتقدم على `reps.QUESTIONS`)، `passes`
(`kind`: `replace` بسؤال واحد بلا تصويت أو `add` بأغلبية ثلاث إجابات لأن النموذج غير حتمي؛ مع `src` و`dst` و`lessons` و`previous` و`questions`)،
و`continuation` (`dst` و`groups` بمصادر مرتبة وأسئلة، وعتبات الصورة). `reps.run` يشغّل الكل مستأنَفًا، و`reps.evaluate` يقيس الإصدارات على
الذهبي. ربطها بخادم الرؤية المحلي وبمرحلة في سطر الأوامر يأتي مع مشغّلي الرؤية.

## المصدر والحالة

كل حقل مستخرج غلاف `{value, source, status}`: المصدر `guide` أو `derived` أو `library` أو `teacher`، والحالة `ok` أو `review` أو `missing`
(`fields.py`). الحدود والصفحات `derived`؛ نص الهدف `guide` ومستوى بلوم `derived` من `bloom_lexicon_ar.json`، والفعل خارج المعجم
`unclassified` ولا يُخمَّن. المثال `ok` إن شهد له مصدران مستقلان أو شارة مقتصّة، وإلا `review`.

## المدقّقات (`checks.py`)

مجموع التمارين المدّعى مقابل سلسلة أرقام OCR مستقلة عنه (فرق واحد مقبول أو تطابق «دليل المهام»)، وأسئلة اختبار الدرس مقابل أعماقها
(أرقام متصلة من 1، عمق 1 إلى 3، ورموز الصفوف هي رموز الصفحة). المدقّق بلا بيانات يعيد `None` ولا يُحسب نجاحًا.

## وراثة الإعداد واللغة والترقيم

- `extends: <اسم>` في `book.yaml` يرث ملف عائلة من `tools/extraction/families/<اسم>.yaml` (أو مسارًا نسبيًا لمجلد الملف)، والدمج
  مفتاحًا مفتاحًا: الخرائط تُدمج والقوائم والقيم يستبدلها الكتاب كلها؛ دورة الوراثة خطأ. العائلة الجاهزة: `ar_teacher_guide`.
- معجم بلوم لكل لغة: `bloom_lexicon: <اسم أو مسار>`، وبدونه `bloom_lexicon_<اللغة>.json` في مجلد الأداة؛ غيابه خطأ عند التحميل.
- شكل رمز الدرس `layout.id_format` (الافتراضي `{unit}.{lesson}`) ونمط قراءته من الافتتاحية `layout.id_pattern` بمجموعتين.

## التصحيحات اليدوية (`corrections.py`)

`corrections.yaml` في مجلد الكتاب: كل تصحيح `stage` و`path` (قائمة: أرقام فهارس ونصوص مفاتيح) و`value` و`reason` إلزامي (8 أحرف فأكثر)
و`expect` اختياري. يُطبَّق على مخرج مرحلته بعد بنائه فيصمد لإعادة الاستخراج، ويُثبَّت ما طُبِّق في `corrections` بالمخرج بقبله وبعده
وسببه، وغلاف الحقل المصحَّح يصير `teacher/ok`. تصحيح لا يصيب شيئًا أو تغيّرت قيمته المتوقعة خطأ صريح (رمز الخروج 3).

## الأختام

كل مرحلة تحسب تجزئة مدخلها (الإعداد المدموج والتصحيحات ومحتوى المجلدات والنواتج السابقة وملف PDF) وتحفظها في `.stamps.json`
بمجلد الكتاب، وتتخطى نفسها إن طابق الختم وكان ناتجها موجودًا؛ `--force` يعيد التشغيل.
