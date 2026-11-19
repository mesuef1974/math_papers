"""حصص الخطة الفصلية: كل بند في الخطة يُفرَد حصصًا مرقّمة. حتمي، بلا Django.

الحصة قيمة مشتقة لا جدول: تُشتق من بنود الخطة بترتيب الأسابيع ثم ترتيب البنود في الأسبوع، فالدرس الممتد على أسبوعين
حصصه متصلة الترقيم (`k` من `n`). التاريخ ليس منها: يأتي من محرك التقويم لشعبة بعينها، فالتحضير واحد للمقرر والتاريخ لكل شعبة.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .semester_plan import PlanEntry, TermPlan


@dataclass(frozen=True)
class PlanPeriod:
    course: str  # معرّف المقرر
    entry: PlanEntry  # البند الذي تنتمي إليه في أسبوعها
    k: int  # رقمها في بندها (الدرس أو المراجعة...) عبر الأسابيع، من 1
    n: int  # عدد حصص البند في الخطة كلها
    number: int  # رقمها في الفصل، من 1
    week: int  # رقم أسبوع الخطة

    @property
    def kind(self) -> str:
        return self.entry.kind

    @property
    def lesson(self) -> str | None:
        return self.entry.lesson

    @property
    def key(self) -> str:
        """مفتاح البند المشترك بين أسابيعه، مثل «lesson:2.3»."""
        return self.entry.key


def plan_periods(course: str, plan: TermPlan) -> tuple[PlanPeriod, ...]:
    """حصص الخطة كلها بترتيبها: لكل بند حصص بعدد `periods`، وترقيم `k` متصل لكل مفتاح بند عبر الأسابيع."""
    totals = Counter()
    for week in plan.weeks:
        for entry in week.entries:
            totals[entry.key] += entry.periods
    seen: Counter[str] = Counter()
    periods: list[PlanPeriod] = []
    for week in plan.weeks:
        for entry in week.entries:
            for _ in range(entry.periods):
                seen[entry.key] += 1
                periods.append(
                    PlanPeriod(
                        course=course,
                        entry=entry,
                        k=seen[entry.key],
                        n=totals[entry.key],
                        number=len(periods) + 1,
                        week=week.n,
                    )
                )
    return tuple(periods)
