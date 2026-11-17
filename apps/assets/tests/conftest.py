import struct
import zlib

import pytest
from django.contrib.auth import get_user_model

from apps.papers.access import ensure_teacher


def make_png(width: int = 4, height: int = 3, shade: int = 0) -> bytes:
    """PNG صالح صغير؛ shade يغيّر البيكسلات فتتغير التجزئة."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    raw = b"".join(b"\x00" + bytes([shade % 256]) * width for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    )


@pytest.fixture(autouse=True)
def local_store(settings, tmp_path):
    settings.ASSETS_STORAGE = "local"
    settings.ASSETS_LOCAL_ROOT = tmp_path / "store"
    return settings.ASSETS_LOCAL_ROOT


@pytest.fixture
def teacher_client(client, db):
    teacher, _ = ensure_teacher("teacher", "Rasm-Bayani-2026")  # pragma: allowlist secret
    client.force_login(teacher)
    return client


@pytest.fixture
def outsider_client(client, db):
    password = "Rasm-Bayani-2026"  # pragma: allowlist secret
    user = get_user_model().objects.create_user("outsider", password=password)
    client.force_login(user)
    return client
