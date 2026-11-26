"""قابلية تثبيت الموقع تطبيقًا: حقول المانيفست ونوعه الذي يخدمه به WhiteNoise."""

from __future__ import annotations

import json

from django.conf import settings
from whitenoise.middleware import WhiteNoiseMiddleware

MANIFEST = settings.BASE_DIR / "frontend" / "public" / "site.webmanifest"


def test_manifest_has_install_fields():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert (manifest.get("id"), manifest.get("start_url"), manifest.get("scope")) == ("/", "/", "/")
    sizes = {icon["sizes"] for icon in manifest["icons"] if icon.get("purpose", "any") == "any"}
    assert {"192x192", "512x512"} <= sizes
    for icon in manifest["icons"]:
        assert (MANIFEST.parent / icon["src"].removeprefix(settings.STATIC_URL)).is_file()


def test_whitenoise_serves_manifest_type():
    assert settings.WHITENOISE_MIMETYPES[".webmanifest"] == "application/manifest+json"
    middleware = WhiteNoiseMiddleware(lambda request: None)
    assert middleware.media_types.get_type("site.webmanifest") == "application/manifest+json"
