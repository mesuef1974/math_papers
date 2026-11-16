# طبقة الأتمتة

دورة البطاقة (16 خطوة في مخطط المشروع) مُنفَّذة هنا بثلاثة أجزاء:

1. `ledger.py` — دفتر أحداث append-only بصيغة JSONL في `automation/ledger/`. البطاقة = سلسلة أحداث
   (`created → ready → claimed → coded → prepush_ok → pr_opened → ci_green → approved → merged → deployed`).
   لا تُحرَّر الأحداث؛ تُضاف فقط. الحالة الحالية = آخر حدث.
2. `runner.py` — مشغّل مجدوَل (cron / Task Scheduler) بقفل ملفّي: يلتقط بطاقة `ready`، ينشئ `git worktree`
   في `.worktrees/<card>`، يشغّل `claude -p` بصلاحيات مخفَّضة (لا push ولا gh merge ولا railway)،
   ثم يشغّل `scripts/prepush_check.py`، ويفتح PR بنفسه (المشغّل هو من يدفع، لا النموذج)، ويسجّل كل خطوة في الدفتر.
3. `scripts/` — البوابات: `prepush_check.py` محليًا، وفي CI: `pr_approval_head_check.py` (اعتماد مربوط بالـ SHA)،
   `check_migration_collisions.py`، `deploy_window.py` (حالة «نافذة النشر» المطلوبة على main)، و`merge_gate.py` (قرار auto-merge).

## الأوامر

```bash
python automation/ledger.py new "عنوان البطاقة" --body "وصف ما يجب فعله وما يُعدّ نجاحًا"
python automation/ledger.py ready <card_id>
python automation/ledger.py list
python automation/ledger.py show <card_id>
python automation/runner.py --once            # يلتقط بطاقة واحدة
python automation/runner.py --dry-run         # يعرض ما سيفعله دون تنفيذ
python automation/schedule.py install         # مهمة MathPapers-Runner المخفية كل 5 دقائق (ببايثون .venv)
python automation/schedule.py status          # آخر تشغيل ونتيجته
python automation/schedule.py remove
```

## الجدولة والاستهلاك

- المهمة تشغّل `runner.py` من المجلد الرئيسي للمشروع، فبعد دمج أي تغيير في `automation/` حدّث المجلد الرئيسي
  (`git merge --ff-only origin/main`) وإلا بقي المشغّل على نسخته القديمة.
- بلا بطاقة `ready` لا يُستدعى النموذج: التشغيل الدوري لا يستهلك توكنات. الاستهلاك يبدأ حين تضع بطاقة بـ `ledger.py ready`،
  وسقفه `--max-turns` (40)؛ والنموذج الأرخص يُحدَّد بـ `install --model <id>`.
- الجلسة الآلية تعمل بقائمة صلاحيات صريحة (`ALLOWED_TOOLS`: تعديل الملفات و`python` و`pytest` و`ruff` و`npm --prefix frontend`
  و`git add/commit/status/diff/log`)، ومخرجاتها في `.worktrees/<card>.log`. فرع بلا إيداع أو بتعديلات غير مودَعة يُسجَّل
  `blocked` ولا يُدفع. قاعدة الاختبار SQLite مؤقتة خارج المستودع إن لم يُضبط `DATABASE_URL`.

## قواعد التصميم (من دروس مشروع المدرسة)

- النموذج لا يرى `git push` ولا `gh pr merge` ولا `railway`: المشغّل يفعلها بعد نجاح الفحص المحلي فقط.
- النجاح الشكلي خطر: `prepush_check.py` يفشل برمز 3 إن غابت أداة بدل أن ينجح صامتًا.
- ملفات CI وlockfiles وسكربتات البوابات محظورة على الدمج الآلي (`merge_gate.ALWAYS_FORBIDDEN`) حتى لا يعدّل النموذج حارسه.
- الاعتماد البشري مرة واحدة لكل بطاقة، في وصف الطلب، مربوط برأسه؛ أي دفع لاحق يُبطله.
- الدمج بـ auto-merge تفعّله `merge_gate.py --enable` بعد الاعتماد؛ نافذة النشر تُفرض بحالة إيداع مطلوبة على main (لا طابور دمج لحساب شخصي).
