from .base import *  # noqa: F403
from .base import env, env_bool

DEBUG = False

# خلف وكيل Railway: الطلب يصل HTTP والـ X-Forwarded-Proto يحمل https.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
# فحص صحة Railway يطلب /health/ بـ HTTP من داخل الشبكة بلا X-Forwarded-Proto ولا يقبل إلا 200: تحويله 301 يُفشل
# كل نشر (حادثة 2026-11-16). الاستثناء لمسار الصحة وحده، وجسمه بلا أسرار؛ كل مسار آخر يبقى محوَّلًا إلى HTTPS.
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
TRUSTED_PROXY_COUNT = int(env("TRUSTED_PROXY_COUNT", "1"))
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False

if not env("ALLOWED_HOSTS"):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("ALLOWED_HOSTS مطلوب في الإنتاج")

if not env("DATABASE_URL"):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("DATABASE_URL مطلوب في الإنتاج")
