"""جسر قرار ما بعد الحصة إلى الأوراق: ورقة علاجية من مولّدات الدرس نفسه. لا نص كتاب ولا توكنز."""

from __future__ import annotations

from datetime import datetime

from django.contrib.auth.models import AbstractBaseUser

from apps.papers import services as papers

from .domain.calendar_engine import PlanningError
from .domain.feedback import ClassOutcome, Decision
from .domain.lesson_run import LessonRun
from .models import ClassOutcomeRecord, LessonRunRecord

REMEDIAL_PER_PERIOD = 5  # أسئلة لكل حصة إعادة تدريس؛ المراجعة السريعة بلا حصة تأخذ حصة واحدة في الحساب


def remedial_worksheet(decision: Decision, seed: int | None = None) -> dict | None:
    """ورقة علاجية (مستوى سهل) للدرس بحسب القرار؛ لا ورقة عند التقدّم. الدرس المجهول يرفع `UnknownLessonError`."""
    if decision.action == "advance":
        return None
    count = REMEDIAL_PER_PERIOD * max(decision.extra_periods, 1)
    return papers.build_worksheet(decision.lesson_id, count, seed, purpose="remedial")


def _section(value: str) -> str:
    section = value.strip()
    if not section or len(section) > 20:
        raise PlanningError("الشعبة مطلوبة وبحد أقصى 20 حرفًا")
    return section


def record_outcome(
    owner: AbstractBaseUser, section: str, outcome: ClassOutcome
) -> tuple[ClassOutcomeRecord, bool]:
    """يحفظ آخر نتيجة لشعبة في درس؛ idempotent: التكرار يحدّث السجل نفسه ولا يضاعفه."""
    return ClassOutcomeRecord.objects.update_or_create(
        owner=owner,
        section=_section(section),
        lesson_code=outcome.lesson_id,
        defaults={
            "attempted": outcome.attempted,
            "correct": outcome.correct,
            "pace": outcome.pace,
            "obstacles": sorted(outcome.obstacles),
        },
    )


def save_run_report(
    owner: AbstractBaseUser, section: str, lesson_code: str, run: LessonRun, started_at: datetime
) -> tuple[LessonRunRecord, bool]:
    """يحفظ تقرير حصة (المخطط مقابل الفعلي لكل طور)؛ المفتاح بداية الحصة فتكرار الحفظ لا يضاعف التقرير."""
    return LessonRunRecord.objects.update_or_create(
        owner=owner,
        section=_section(section),
        lesson_code=lesson_code,
        started_at=started_at,
        defaults={
            "period_minutes": run.flow.period_minutes,
            "finished": run.finished,
            "phases": [
                {"phase": c.phase, "planned": c.planned, "actual": round(c.actual, 2), "skipped": c.skipped}
                for c in run.closed
            ],
        },
    )
