"""طبقة تخزين الملفات الواحدة: put/get/exists/delete بمفتاح نصي. قرص محلي للتطوير، وحاوية S3 للإنتاج.

المفتاح مسار نسبي بشرطات مائلة (`assets/<مقرر>/<درس>/...`)؛ ما يخرج من الجذر أو يحوي `..` يُرفض.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from django.conf import settings

from . import sigv4

TIMEOUT = 30


class StorageError(RuntimeError):
    pass


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...


def check_key(key: str) -> str:
    parts = key.split("/")
    if not key or key.startswith("/") or "\\" in key or any(p in ("", ".", "..") for p in parts):
        raise StorageError(f"مفتاح تخزين غير صالح: {key!r}")
    return key


class LocalStorage:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / check_key(key)).resolve()
        if self.root not in path.parents:
            raise StorageError(f"مفتاح خارج الجذر: {key!r}")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)  # كتابة ذرّية: لا يرى قارئ نصف ملف

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as error:
            raise StorageError(f"لا ملف بالمفتاح {key}") from error

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    """حاوية متوافقة مع S3 بطلبات موقّعة SigV4. الحاوية خاصة: لا رابط عام، والتقديم من التطبيق وحده."""

    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        region: str,
        access_key: str,
        secret_key: str,
        path_style: bool = False,
    ):
        if not (endpoint and bucket and access_key and secret_key):
            raise StorageError("إعداد S3 ناقص: ASSETS_S3_ENDPOINT/BUCKET/ACCESS_KEY_ID/SECRET_ACCESS_KEY")
        parts = urlsplit(endpoint)
        self.scheme = parts.scheme or "https"
        if self.scheme not in ("http", "https"):
            raise StorageError(f"مخطط عنوان S3 غير مسموح: {self.scheme}")
        self.bucket, self.region = bucket, region
        self.access_key, self.secret_key = access_key, secret_key
        self.path_style = path_style
        self.host = parts.netloc or parts.path
        if not path_style:
            self.host = f"{bucket}.{self.host}"

    def _request(self, method: str, key: str, payload: bytes | None = None, content_type: str = "") -> bytes:
        check_key(key)
        path = f"/{self.bucket}/{key}" if self.path_style else f"/{key}"
        extra = {"content-type": content_type} if content_type else {}
        headers = sigv4.sign_headers(
            method=method,
            host=self.host,
            path=path,
            payload=payload,
            access_key=self.access_key,
            secret_key=self.secret_key,
            region=self.region,
            now=datetime.now(UTC),
            extra_headers=extra,
        )
        headers.pop("host")  # urllib يضيفها من العنوان
        url = f"{self.scheme}://{self.host}{sigv4.canonical_path(path)}"
        request = urllib.request.Request(url, data=payload, method=method, headers=headers)  # noqa: S310 — المخطط http/https من الإعداد
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 — العنوان من الإعداد لا من المستخدم
            return response.read()

    def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self._request("PUT", key, data, content_type)
        except urllib.error.URLError as error:
            raise StorageError(f"فشل رفع {key}: {error}") from error

    def get(self, key: str) -> bytes:
        try:
            return self._request("GET", key)
        except urllib.error.HTTPError as error:
            raise StorageError(f"لا ملف بالمفتاح {key} ({error.code})") from error
        except urllib.error.URLError as error:
            raise StorageError(f"فشل قراءة {key}: {error}") from error

    def exists(self, key: str) -> bool:
        try:
            self._request("HEAD", key)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return False
            raise StorageError(f"فشل فحص {key} ({error.code})") from error
        except urllib.error.URLError as error:
            raise StorageError(f"فشل فحص {key}: {error}") from error
        return True

    def delete(self, key: str) -> None:
        try:
            self._request("DELETE", key)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise StorageError(f"فشل حذف {key} ({error.code})") from error
        except urllib.error.URLError as error:
            raise StorageError(f"فشل حذف {key}: {error}") from error


def get_storage() -> Storage:
    backend = settings.ASSETS_STORAGE
    if backend == "local":
        return LocalStorage(settings.ASSETS_LOCAL_ROOT)
    if backend == "s3":
        return S3Storage(
            endpoint=settings.ASSETS_S3_ENDPOINT,
            bucket=settings.ASSETS_S3_BUCKET,
            region=settings.ASSETS_S3_REGION,
            access_key=settings.ASSETS_S3_ACCESS_KEY_ID,
            secret_key=settings.ASSETS_S3_SECRET_ACCESS_KEY,
            path_style=settings.ASSETS_S3_PATH_STYLE,
        )
    raise StorageError(f"ASSETS_STORAGE غير معروف: {backend}")
