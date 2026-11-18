# طبقة الأتمتة

دورة البطاقة (16 خطوة في مخطط المشروع) مُنفَّذة هنا بأربعة أجزاء:

1. `ledger.py` — دفتر أحداث append-only بصيغة JSONL في `automation/ledger/`. البطاقة = سلسلة أحداث
   (`created → ready → claimed → coded → prepush_ok → pr_opened → ci_green → approved → merged → deployed`).
   لا تُحرَّر الأحداث؛ تُضاف فقط. الحالة الحالية = آخر حدث.
2. `runner.py` — مشغّل مجدوَل (cron / Task Scheduler) بقفل ملفّي: يلتقط بطاقة `ready`، ينشئ `git worktree`
   في `.worktrees/<card>`، يشغّل `claude -p` بصلاحيات مخفَّضة (لا push ولا gh merge ولا railway)،
   ثم يشغّل `scripts/prepush_check.py`، ويفتح PR بنفسه (المشغّل هو من يدفع، لا النموذج)، ويسجّل كل خطوة في الدفتر.
3. `sync.py` — مزامنة الدفتر مع GitHub: طلب مدموج على فرع `card/<المعرّف>` يكتب `merged`، وطلب مفتوح لم يُسجَّل يكتب
   `pr_opened`. المشغّل يستدعيها في كل تشغيل (بلا بطاقة معلّقة لا يُستدعى `gh`). `deployed` يبقى حدثًا يدويًا: النشر على
   Railway لا يُعرف من GitHub، وطلب أُغلق بلا دمج يُعرض ولا يُكتب له حدث.
4. `scripts/` — البوابات: `prepush_check.py` محليًا، وفي CI: `pr_approval_head_check.py` (اعتماد مربوط بالـ SHA)،
   `check_migration_collisions.py`، `deploy_window.py` (حالة «نافذة النشر» المطلوبة على main)، و`merge_gate.py` (قرار auto-merge).

## الأوامر

```bash
python automation/ledger.py new "عنوان البطاقة" --body "وصف ما يجب فعله وما يُعدّ نجاحًا"
python automation/ledger.py ready <card_id>
python automation/ledger.py list [--state <حالة>]   # بلا الخيار كل البطاقات؛ به بطاقات تلك الحالة وحدها
python automation/ledger.py show <card_id>
python automation/runner.py --once            # يلتقط بطاقة واحدة
python automation/runner.py --dry-run         # يعرض ما سيفعله دون تنفيذ
python automation/sync.py [--apply]           # أحداث merged/pr_opened من حالة الطلبات؛ بلا --apply عرض فقط
python automation/sync.py --worktrees         # أشجار وفروع البطاقات المنتهية (عرض فقط، الحذف بيد المالك)
python automation/schedule.py install         # مهمة MathPapers-Runner المخفية كل 5 دقائق (ببايثون .venv)
python automation/schedule.py status          # آخر تشغيل ونتيجته
python automation/schedule.py remove
```

## الجدولة والاستهلاك

- المهمة تشغّل `runner.py` من المجلد الرئيسي للمشروع، فبعد دمج أي تغيير في `automation/` حدّث المجلد الرئيسي
  (`git merge --ff-only origin/main`) وإلا بقي المشغّل على نسخته القديمة.
- `conhost --headless` لا يعيد رمز الخروج، فـ«Last Result» في Task Scheduler صفر دائمًا. الدليل أن المشغّل يعمل سطر لكل تشغيل
  في `.worktrees/runner.log` (آخر 200)، يذكر ما انتهى إليه وأي أداة (`claude` أو `git` أو `gh`) غابت عن المسار، ويعرض
  `schedule.py status` آخره.
- بلا بطاقة `ready` لا يُستدعى النموذج: التشغيل الدوري لا يستهلك توكنات. الاستهلاك يبدأ حين تضع بطاقة بـ `ledger.py ready`،
  وسقفه `--max-turns` (40)؛ والنموذج الأرخص يُحدَّد بـ `install --model <id>`.
- الجلسة الآلية تعمل بقائمة صلاحيات صريحة (`ALLOWED_TOOLS`: تعديل الملفات و`python manage.py` و`python -m pytest|ruff`
  و`python scripts/prepush_check.py` و`pytest` و`ruff` و`npm --prefix frontend` و`git add/commit/status/diff/log`؛ لا `python` مطلق
  ولا `gh`)، ومخرجاتها في `.worktrees/<card>.log`. القائمة تضيّق ولا تعزل (اختبار يكتبه النموذج يشغّل ما يشاء)، فبيئة
  الجلسة نفسها بلا نشر (`model_env`): عنوان الدفع معطَّل لـ git، ورمز `gh` غير صالح يسبق الرمز المخزَّن.
- ما لا يُدفع يُسجَّل `blocked`: فرع بلا إيداع، أو بتعديلات غير مودَعة، أو يمسّ مسارًا من `merge_gate.ALWAYS_FORBIDDEN`
  (الفحص المحلي يُشغَّل من نسخة الفرع، ففرع عدّل حارسه لا يشهد لنفسه؛ دفعه بيد المالك).
- فحص المشغّل صارم: بلا `--allow-missing`، ولا دفع إلا ببصمة `.prepush_receipt` على رأس الفرع نفسه كل فحوصها `ok`؛ وما قيس
  يُكتب في حدث `prepush_ok`. قاعدة الاختبار SQLite مؤقتة خارج المستودع إن لم يُضبط `DATABASE_URL`.

## قواعد التصميم (من دروس مشروع المدرسة)

- النموذج لا يرى `git push` ولا `gh` ولا `railway`: المشغّل يفعلها بعد نجاح الفحص المحلي فقط. والجلسات التفاعلية يحجب
  حارسها كل `git push` إلا بإذن المالك المكتوب في `GUARD_GIT_ALLOW`.
- النجاح الشكلي خطر: `prepush_check.py` يفشل برمز 3 إن غابت أداة بدل أن ينجح صامتًا.
- ملفات CI وlockfiles وسكربتات البوابات والحارس والمشغّل نفسه (`automation/*.py`) محظورة على الدمج الآلي
  (`merge_gate.ALWAYS_FORBIDDEN`) حتى لا يعدّل النموذج حارسه.
- الاعتماد البشري مرة واحدة لكل بطاقة، في وصف الطلب، مربوط برأسه؛ أي دفع لاحق يُبطله.
- الدمج بـ auto-merge تفعّله `merge_gate.py --enable` بعد الاعتماد؛ نافذة النشر تُفرض بحالة إيداع مطلوبة على main (لا طابور دمج لحساب شخصي).
