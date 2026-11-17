"""توقيع AWS Signature Version 4 لطلبات S3 بالترويسة (Authorization). مكتبة قياسية فقط: لا boto3 ولا تعديل لـ lockfile.

الخوارزمية منشورة: طلب قانوني، ثم سلسلة توقيع، ثم مفتاح مشتق من السر بسلسلة HMAC-SHA256. يثبّتها اختبار على المثال المنشور في وثائق AWS.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from urllib.parse import quote

ALGORITHM = "AWS4-HMAC-SHA256"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def signing_key(secret: str, date: str, region: str, service: str = "s3") -> bytes:
    key = _hmac(("AWS4" + secret).encode("utf-8"), date)
    for part in (region, service, "aws4_request"):
        key = _hmac(key, part)
    return key


def canonical_path(path: str) -> str:
    """مسار S3: يُرمَّز مرة واحدة (الشرطة المائلة محفوظة)."""
    return quote(path or "/", safe="/-_.~")


def canonical_query(params: dict[str, str]) -> str:
    return "&".join(f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(params.items()))


def sign_headers(
    *,
    method: str,
    host: str,
    path: str,
    payload: bytes | None,
    access_key: str,
    secret_key: str,
    region: str,
    now: datetime,
    query: dict[str, str] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """يرجع ترويسات الطلب كاملة بما فيها Authorization (و x-amz-date و x-amz-content-sha256)."""
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = amz_date[:8]
    payload_hash = EMPTY_SHA256 if not payload else hashlib.sha256(payload).hexdigest()
    headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    headers.update({k.lower(): v.strip() for k, v in (extra_headers or {}).items()})
    names = sorted(headers)
    canonical_headers = "".join(f"{n}:{headers[n]}\n" for n in names)
    signed = ";".join(names)
    request = "\n".join(
        [method, canonical_path(path), canonical_query(query or {}), canonical_headers, signed, payload_hash]
    )
    scope = f"{date}/{region}/s3/aws4_request"
    to_sign = "\n".join([ALGORITHM, amz_date, scope, hashlib.sha256(request.encode("utf-8")).hexdigest()])
    signature = hmac.new(
        signing_key(secret_key, date, region), to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    headers["authorization"] = (
        f"{ALGORITHM} Credential={access_key}/{scope}, SignedHeaders={signed}, Signature={signature}"
    )
    return headers
