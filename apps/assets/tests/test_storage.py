"""طبقة التخزين: التوقيع على أمثلة AWS المنشورة، والقرص المحلي، وS3 على خادم مزيَّف يتحقق من التوقيع."""

import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote, urlsplit

import pytest

from apps.assets import sigv4
from apps.assets.storage import LocalStorage, S3Storage, StorageError, check_key, get_storage

AWS_ACCESS = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # pragma: allowlist secret — مثال وثائق AWS


def test_signing_key_matches_the_published_aws_example():
    secret = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"  # pragma: allowlist secret
    expected = "f4780e2d9f65fa895f9c67b32ce1baf0b0d8a43505a000a1a9e090d414db404d"  # pragma: allowlist secret
    assert sigv4.signing_key(secret, "20120215", "us-east-1", "iam").hex() == expected


def test_get_object_signature_matches_the_published_aws_example():
    headers = sigv4.sign_headers(
        method="GET",
        host="examplebucket.s3.amazonaws.com",
        path="/test.txt",
        payload=None,
        access_key=AWS_ACCESS,
        secret_key=AWS_SECRET,
        region="us-east-1",
        now=datetime(2013, 5, 24, tzinfo=UTC),
        extra_headers={"Range": "bytes=0-9"},
    )
    assert headers["authorization"].endswith(
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )
    assert "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date" in headers["authorization"]


def test_put_object_signature_matches_the_published_aws_example():
    headers = sigv4.sign_headers(
        method="PUT",
        host="examplebucket.s3.amazonaws.com",
        path="/test$file.text",
        payload=b"Welcome to Amazon S3.",
        access_key=AWS_ACCESS,
        secret_key=AWS_SECRET,
        region="us-east-1",
        now=datetime(2013, 5, 24, tzinfo=UTC),
        extra_headers={"Date": "Fri, 24 May 2013 00:00:00 GMT", "x-amz-storage-class": "REDUCED_REDUNDANCY"},
    )
    assert headers["authorization"].endswith(
        "Signature=98ad721746da40c64f1a55b78f14c238d841ea1380cd77a1b5971af0ece108bd"
    )


# --- القرص المحلي ---


@pytest.mark.parametrize("key", ["", "/abs", "a/../b", "a//b", "a\\b", "./a", "../a"])
def test_bad_keys_are_rejected(key):
    with pytest.raises(StorageError):
        check_key(key)


def test_local_roundtrip_and_overwrite(tmp_path):
    store = LocalStorage(tmp_path / "root")
    assert not store.exists("a/b.png")
    store.put("a/b.png", b"one", "image/png")
    store.put("a/b.png", b"two", "image/png")
    assert store.exists("a/b.png") and store.get("a/b.png") == b"two"
    assert not list((tmp_path / "root").rglob("*.tmp"))
    store.delete("a/b.png")
    store.delete("a/b.png")  # حذف ما لا وجود له لا يفشل
    assert not store.exists("a/b.png")
    with pytest.raises(StorageError):
        store.get("a/b.png")


def test_get_storage_picks_backend_from_settings(settings, tmp_path):
    settings.ASSETS_STORAGE = "local"
    settings.ASSETS_LOCAL_ROOT = tmp_path
    assert isinstance(get_storage(), LocalStorage)
    settings.ASSETS_STORAGE = "s3"
    settings.ASSETS_S3_ENDPOINT = ""
    with pytest.raises(StorageError, match="ناقص"):
        get_storage()
    settings.ASSETS_STORAGE = "nope"
    with pytest.raises(StorageError, match="غير معروف"):
        get_storage()


# --- S3 على خادم مزيَّف ---


class FakeS3(BaseHTTPRequestHandler):
    objects: dict[str, bytes] = {}
    secret = "server-secret"  # pragma: allowlist secret
    access = "server-access"

    def log_message(self, *args):
        pass

    def _verify(self, payload: bytes) -> bool:
        auth = self.headers.get("authorization", "")
        amz_date = self.headers.get("x-amz-date", "")
        extra = {"content-type": self.headers["content-type"]} if self.headers.get("content-type") else {}
        # لا ترويسة content-type مُوقَّعة في GET/HEAD/DELETE: نقارن بما أُرسل فعلًا
        expected = sigv4.sign_headers(
            method=self.command,
            host=self.headers["host"],
            path=unquote(urlsplit(self.path).path),
            payload=payload,
            access_key=self.access,
            secret_key=self.secret,
            region="auto",
            now=datetime.strptime(amz_date, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC),
            extra_headers=extra,
        )["authorization"]
        return auth == expected

    def _handle(self):
        length = int(self.headers.get("content-length") or 0)
        payload = self.rfile.read(length) if length else b""
        if not self._verify(payload):
            self.send_response(403)
            self.send_header("content-length", "0")
            self.end_headers()
            return
        key = unquote(urlsplit(self.path).path)
        body = b""
        if self.command == "PUT":
            self.objects[key] = payload
            status = 200
        elif self.command == "DELETE":
            self.objects.pop(key, None)
            status = 204
        elif key in self.objects:
            status, body = 200, self.objects[key]
        else:
            status = 404
        self.send_response(status)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    do_GET = do_PUT = do_HEAD = do_DELETE = _handle  # noqa: N815 — أسماء مفروضة من BaseHTTPRequestHandler


@pytest.fixture
def fake_s3():
    FakeS3.objects = {}
    server = HTTPServer(("127.0.0.1", 0), FakeS3)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def _s3(endpoint, secret=FakeS3.secret):
    return S3Storage(
        endpoint=endpoint,
        bucket="bkt",
        region="auto",
        access_key=FakeS3.access,
        secret_key=secret,
        path_style=True,
    )


def test_s3_roundtrip_with_verified_signatures(fake_s3):
    store = _s3(fake_s3)
    assert not store.exists("assets/g10/1.1/example1-0-abc.png")
    store.put("assets/g10/1.1/example1-0-abc.png", b"\x89PNG data", "image/png")
    assert FakeS3.objects == {"/bkt/assets/g10/1.1/example1-0-abc.png": b"\x89PNG data"}
    assert store.exists("assets/g10/1.1/example1-0-abc.png")
    assert store.get("assets/g10/1.1/example1-0-abc.png") == b"\x89PNG data"
    store.delete("assets/g10/1.1/example1-0-abc.png")
    store.delete("assets/g10/1.1/example1-0-abc.png")
    assert not store.exists("assets/g10/1.1/example1-0-abc.png")
    with pytest.raises(StorageError, match="404"):
        store.get("assets/g10/1.1/example1-0-abc.png")


def test_s3_wrong_secret_is_rejected(fake_s3):
    bad = _s3(fake_s3, secret="wrong")  # pragma: allowlist secret
    with pytest.raises(StorageError):
        bad.put("k/a.png", b"x", "image/png")
    with pytest.raises(StorageError, match="403"):
        bad.exists("k/a.png")
    assert FakeS3.objects == {}


def test_s3_virtual_host_style_puts_bucket_in_host_and_rejects_bad_scheme():
    store = S3Storage(
        endpoint="https://storage.example.com",
        bucket="bkt",
        region="auto",
        access_key="a",
        secret_key="b",  # pragma: allowlist secret
    )
    assert store.host == "bkt.storage.example.com"
    with pytest.raises(StorageError, match="مخطط"):
        S3Storage(
            endpoint="file:///etc", bucket="b", region="auto", access_key="a", secret_key="b"
        )  # pragma: allowlist secret
