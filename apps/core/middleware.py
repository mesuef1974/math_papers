"""وسيطان صغيران: معرّف طلب يولَّد في الخادم، وترويسات أمن لا يوفرها Django بنفسه.

معرّف الطلب لا يُقرأ من العميل أبدًا: ترويسة X-Request-ID من مجهول كانت تُستعمل مفتاح تكرار في سجل التدقيق،
فيستطيع المهاجم تثبيتها ليُسجَّل فشل واحد بدل مئة. هنا يُولَّد المعرّف لكل طلب ويُعاد في الاستجابة للتتبع.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

REQUEST_ID_HEADER = "X-Request-ID"


def request_id_of(request: HttpRequest) -> str:
    """المعرّف الذي وضعه الوسيط؛ سلسلة فارغة خارج دورة الطلب (الاختبارات المباشرة للخدمات)."""
    return getattr(request, "request_id", "")


class RequestIDMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.request_id = uuid.uuid4().hex  # type: ignore[attr-defined]
        response = self.get_response(request)
        response[REQUEST_ID_HEADER] = request.request_id  # type: ignore[attr-defined]
        return response


class SecurityHeadersMiddleware:
    """Content-Security-Policy وPermissions-Policy. تُعطَّل CSP بجعل SECURITY_CSP فارغة (التطوير مع HMR)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.csp = getattr(settings, "SECURITY_CSP", "")
        self.permissions = getattr(settings, "SECURITY_PERMISSIONS_POLICY", "")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if self.csp and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = self.csp
        if self.permissions and "Permissions-Policy" not in response:
            response["Permissions-Policy"] = self.permissions
        return response
