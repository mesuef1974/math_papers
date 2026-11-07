"""عنوان العميل الحقيقي خلف وكيل موثوق، لقفل المحاولات (django-axes).

خلف وكيل Railway يصل كل طلب من عنوان الوكيل نفسه، فلو قُفل بـ REMOTE_ADDR لقفلت خمس محاولات فاشلة
الجميع. نأخذ المدخل رقم N من يمين X-Forwarded-For حيث N عدد الوكلاء الموثوقين: كل وكيل يضيف عنوانًا
في الآخر، والعميل لا يستطيع إلا أن يضيف في الأول، فلا يمكنه تزوير هذا المدخل.
"""

from __future__ import annotations

from ipaddress import ip_address

from django.conf import settings
from django.http import HttpRequest


def client_ip(request: HttpRequest) -> str | None:
    hops = settings.TRUSTED_PROXY_COUNT
    remote = request.META.get("REMOTE_ADDR")
    if hops <= 0:
        return remote
    chain = [part.strip() for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if part.strip()]
    if len(chain) < hops:
        return remote
    candidate = chain[-hops]
    try:
        return str(ip_address(candidate))
    except ValueError:
        return remote
