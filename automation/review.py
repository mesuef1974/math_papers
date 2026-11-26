"""محطة المراجعة المستقلة: جلسة للقراءة فقط تقرأ فرق البطاقة قبل فتح طلبها وتكتب رأيها في وصفه.

رأي لا بوابة: لا يمنع الطلب ولا يعتمده، وتعذّره لا يُسقط البطاقة. القرار للمالك.
"""

from __future__ import annotations

import shutil

# أقوى من نموذج التنفيذ عمدًا: المراجعة لا تُقصَّر (قرار المالك 2026-11-19).
REVIEW_MODEL = "claude-opus-5-5"
REVIEW_TURNS = 25
REVIEW_TIMEOUT = 20 * 60
REVIEW_LIMIT = 4000
READ_ONLY = ["Read", "Glob", "Grep", "Bash(git diff*)", "Bash(git log*)"]
DENIED = ["Edit", "Write", "Bash(git push*)", "Bash(gh *)", "Bash(railway*)"]

PROMPT = """أنت مراجع مستقل لم تكتب هذا التغيير. اقرأ `git diff origin/main...HEAD` وما يلزم من الملفات، ولا تعدّل شيئًا.

مواصفة البطاقة: {title}
{body}

النجاح: {success}

ابحث عن: خطأ في الصحة (ومنه صحة الرياضيات)، ومخالفة للمواصفة أو قواعد CLAUDE.md، وثغرة أمنية، واختبار لا يثبت ما يدّعيه.
أجب بالعربية في أقل من 300 كلمة. السطر الأول إمّا «الحكم: سليم» أو «الحكم: ملاحظات»، ثم كل ملاحظة بسطر فيه الملف والسطر.
"""


def command(model: str = REVIEW_MODEL) -> list[str]:
    cmd = [shutil.which("claude") or "claude", "-p", "--max-turns", str(REVIEW_TURNS)]
    cmd += ["--model", model, "--output-format", "json"]
    return [*cmd, "--allowedTools", *READ_ONLY, "--disallowedTools", *DENIED]


def sanitize(text: str) -> str:
    """نص النموذج يدخل وصف الطلب: لا يُقلَّد به سطر الاعتماد (يلزمه الشرطة الطويلة) ولا يُنادى به أحد."""
    return text.replace("—", "-").replace("@", "＠").strip()[:REVIEW_LIMIT]


def section(text: str) -> str:
    return f"## مراجعة آلية مستقلة (رأي لا اعتماد)\n{sanitize(text) or 'تعذّرت المراجعة.'}"
