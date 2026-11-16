"""إعدادات الإنتاج الحقيقية (config.settings.production) تُحمَّل في عملية مستقلة: الاختبارات تعمل بإعدادات testing،
فما يخص الإنتاج وحده (التحويل إلى HTTPS) لا يُرى فيها."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROBE = """
import django
django.setup()
from django.conf import settings
from django.middleware.security import SecurityMiddleware
from django.test import RequestFactory

assert settings.SECURE_SSL_REDIRECT is True
middleware = SecurityMiddleware(lambda request: None)
factory = RequestFactory()

# فحص صحة Railway: HTTP صريح بلا X-Forwarded-Proto. لا تحويل، فيصل الطلب إلى العرض ويعيد 200.
assert middleware.process_request(factory.get("/health/")) is None, "health redirected"

# كل مسار آخر يبقى محوَّلًا إلى HTTPS، ومنه ما يشبه مسار الصحة.
for path in ("/", "/api/v1/ping", "/health", "/health/extra", "/x/health/"):
    response = middleware.process_request(factory.get(path))
    assert response is not None and response.status_code == 301, path
    assert response["Location"].startswith("https://"), path

# خلف الوكيل (X-Forwarded-Proto: https) لا تحويل لأي مسار.
assert middleware.process_request(factory.get("/api/v1/ping", HTTP_X_FORWARDED_PROTO="https")) is None
print("ok")
"""


def test_production_exempts_only_health_from_https_redirect(tmp_path):
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "SECRET_KEY": "ci-testing-only",  # pragma: allowlist secret
        "ALLOWED_HOSTS": "testserver",
        "DATABASE_URL": f"sqlite:///{(tmp_path / 'probe.db').as_posix()}",
        "SECURE_SSL_REDIRECT": "1",
        "PYTHONUTF8": "1",
    }
    env.pop("REDIS_URL", None)
    result = subprocess.run(  # noqa: S603 — مفسّر الاختبار نفسه ونص ثابت
        [sys.executable, "-c", PROBE],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().endswith("ok")
