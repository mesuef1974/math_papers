"""حلقة ما بعد الحصة: إتقان المعيار على مستوى الصف يولّد قرارًا ويعدّل الخطة. حتمي، بلا Django ولا توكنز.

المدخل أعداد على مستوى الصف وفئات مغلقة فقط (بيانات الطلاب الفردية خارج النطاق: PDPPL). العتبتان (0.8 و0.5) وحدّ التعثر
الشديد (0.3) افتراضات من المولّد غير مؤكدة من الوزارة ولا من المالك، وتُعدَّل ثوابتَ هنا. القرار لا يغيّر الخطة بنفسه:
`apply_decision` يدرج بند مراجعة بعد الدرس، ثم يستدعي المستدعي `calendar_engine.reflow` فتُزاح الدروس اللاحقة.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .calendar_engine import Item, PlanningError

MASTERED_AT = 0.8
DEVELOPING_AT = 0.5
SEVERE_BELOW = 0.3
PACES = ("fast", "ok", "slow")
OBSTACLES = ("time", "concept", "skill", "resources")
LEVELS = ("mastered", "developing", "not_yet")
ACTIONS = ("advance", "quick_review", "reteach")
RETEACH_SUFFIX = "-reteach"


@dataclass(frozen=True)
class ClassOutcome:
    """نتيجة الصف في بطاقة الخروج أو التقييم البنائي، بأعداد فقط، مع نبض الحصة وعوائقها بفئات مغلقة."""

    lesson_id: str
    attempted: int
    correct: int
    pace: str = "ok"
    obstacles: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.attempted < 1:
            raise PlanningError(f"لا محاولات مسجّلة للدرس {self.lesson_id}")
        if not 0 <= self.correct <= self.attempted:
            raise PlanningError(f"عدد الصحيح خارج المدى للدرس {self.lesson_id}")
        if self.pace not in PACES:
            raise PlanningError(f"نبض غير معروف: {self.pace}")
        if not self.obstacles <= set(OBSTACLES):
            raise PlanningError("عائق غير معروف")

    @property
    def rate(self) -> float:
        return self.correct / self.attempted


@dataclass(frozen=True)
class Decision:
    lesson_id: str
    level: str
    rate: float
    action: str
    extra_periods: int
    notes: tuple[str, ...] = ()


def mastery_level(rate: float) -> str:
    if rate >= MASTERED_AT:
        return "mastered"
    if rate >= DEVELOPING_AT:
        return "developing"
    return "not_yet"


def decide(outcome: ClassOutcome) -> Decision:
    """متقن: تقدّم. نامٍ: مراجعة سريعة في افتتاح الحصة التالية بلا حصة إضافية. دون ذلك: حصة إعادة تدريس (حصتان عند التعثر الشديد)."""
    level = mastery_level(outcome.rate)
    if level == "mastered":
        action, extra = "advance", 0
    elif level == "developing":
        action, extra = "quick_review", 0
    else:
        action, extra = "reteach", 2 if outcome.rate < SEVERE_BELOW else 1
    notes = (
        *(["pace_slow"] if outcome.pace == "slow" else []),
        *(f"obstacle_{o}" for o in sorted(outcome.obstacles)),
    )
    return Decision(outcome.lesson_id, level, outcome.rate, action, extra, tuple(notes))


def apply_decision(items: Iterable[Item], decision: Decision) -> list[Item]:
    """يدرج بند مراجعة بعد الدرس بحصص القرار؛ idempotent: تكرار القرار يستبدل بند المراجعة ولا يضاعفه، وقرار بلا حصص يزيله."""
    items = list(items)
    lesson_ids = [i.id for i in items]
    if decision.lesson_id not in lesson_ids:
        raise PlanningError(f"درس غير موجود في الخطة: {decision.lesson_id}")
    review_id = decision.lesson_id + RETEACH_SUFFIX
    items = [i for i in items if i.id != review_id]
    if decision.extra_periods < 1:
        return items
    at = [i.id for i in items].index(decision.lesson_id) + 1
    items.insert(at, Item(review_id, decision.extra_periods, "review"))
    return items
