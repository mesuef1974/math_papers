"""جسر قرار ما بعد الحصة إلى الأوراق: ورقة علاجية من مولّدات الدرس نفسه. لا نص كتاب ولا توكنز."""

from __future__ import annotations

from apps.papers import services as papers

from .domain.feedback import Decision

REMEDIAL_PER_PERIOD = 5  # أسئلة لكل حصة إعادة تدريس؛ المراجعة السريعة بلا حصة تأخذ حصة واحدة في الحساب


def remedial_worksheet(decision: Decision, seed: int | None = None) -> dict | None:
    """ورقة علاجية (مستوى سهل) للدرس بحسب القرار؛ لا ورقة عند التقدّم. الدرس المجهول يرفع `UnknownLessonError`."""
    if decision.action == "advance":
        return None
    count = REMEDIAL_PER_PERIOD * max(decision.extra_periods, 1)
    return papers.build_worksheet(decision.lesson_id, count, seed, purpose="remedial")
