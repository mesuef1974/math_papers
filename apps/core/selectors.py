"""طبقة القراءة (Selectors): استعلامات فقط، بلا آثار جانبية، مع select_related لتجنّب N+1."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from django.db.models import QuerySet

from .models import AuditLog

Metric = Callable[[], float | None]


def recent_audit(limit: int = 50) -> QuerySet[AuditLog]:
    return AuditLog.objects.select_related("actor").order_by("-created_at")[:limit]


def plan_metric_sources() -> dict[str, Metric]:
    """مصدر كل مؤشر في docs/innovation_plan.yaml له قياس اليوم. المؤشر الغائب هنا لا جدول له بعد فقيمته null؛
    يُضاف سطره حين يُدمج جدوله (نتائج البنود، الأوراق العلاجية، المدارس...) بقراءة ORM تعيد عددًا أو نسبة."""
    from apps.papers import selectors as papers  # الاستيراد هنا: core لا يحمّل المولّدات عند الإقلاع

    return {
        "tagged_objective_formulas_pct": papers.tagged_objective_formulas_pct,
        "lessons_with_error_spotting": papers.lessons_with_error_spotting,
    }


def _number(key: str, value: object) -> float | None:
    """الملف أعداد ونسب فقط: أي قيمة أخرى (نص، قائمة، صف) خطأ في المصدر لا يُكتب."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{key}: قيمة المؤشر ليست عددًا ({type(value).__name__})")
    return value if isinstance(value, int) else round(value, 2)


def plan_metrics(keys: Iterable[str]) -> dict[str, float | None]:
    """قيمة كل مؤشر مطلوب: عدد أو نسبة، و`None` لما لا مصدر له بعد."""
    sources = plan_metric_sources()
    return {key: _number(key, sources[key]()) if key in sources else None for key in keys}
