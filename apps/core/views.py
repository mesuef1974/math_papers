"""عرضان فقط: صحة الخدمة (لـ Railway healthcheck) وقشرة SPA التي يحقن فيها django-vite حزم Vue."""

from __future__ import annotations

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def health(request: HttpRequest) -> JsonResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db = "ok"
        status = 200
    except Exception:  # noqa: BLE001
        db = "down"
        status = 503
    body: dict = {"db": db}
    if db == "ok":
        knowledge = _knowledge_state()
        body["knowledge"] = knowledge
        if any(state in ("stale", "unloaded") for state in knowledge.values()):
            body["status"] = "degraded"
            if settings.KNOWLEDGE_HEALTH_STRICT:
                status = 503
    body.setdefault("status", "ok" if status == 200 else "degraded")
    return JsonResponse(body, status=status)


def _knowledge_state() -> dict[str, str]:
    """حالة المعرفة لكل مقرر؛ عطل في القراءة يُبلَّغ unknown ولا يُسقط الصحة (الصحة للقاعدة أولًا)."""
    from apps.knowledge.selectors import knowledge_state

    try:
        return knowledge_state()
    except Exception:  # noqa: BLE001
        return {"*": "unknown"}


@require_GET
def spa(request: HttpRequest) -> HttpResponse:
    return render(request, "spa.html")
