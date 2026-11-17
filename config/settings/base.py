"""الإعدادات المشتركة. كل ما يختلف بين البيئات يُقرأ من المتغيرات، ولا أسرار في الشيفرة."""

from __future__ import annotations

import os
import re
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(f"المتغير {name} مطلوب")
    return value or ""


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


SECRET_KEY = env("SECRET_KEY", required=True)
DEBUG = False
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
ADMIN_URL = env("ADMIN_URL", "admin/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django_vite",
    "axes",
    "apps.core",
    "apps.curriculum",
    "apps.assets",
    "apps.knowledge",
    "apps.papers",
    "apps.planning",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.RequestIDMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # لا LocaleMiddleware: الموقع عربي أولًا مهما كان Accept-Language للمتصفح.
    # عند الحاجة لتبديل اللغة أضفه مع i18n_patterns، وسيتبعه dir/lang في spa.html تلقائيًا.
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

DATABASES = {
    "default": dj_database_url.config(
        default=env("DATABASE_URL", "postgres://app:app@localhost:5432/app"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # ساعة
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
# عدد الوكلاء الموثوقين أمام التطبيق (Railway = 1). صفر يعني REMOTE_ADDR مباشرة.
TRUSTED_PROXY_COUNT = int(env("TRUSTED_PROXY_COUNT", "0"))
# /health/ يذكر حالة معرفة المقررات دائمًا (knowledge). مع 1 يعيد 503 إن تغيّر المصدر بلا تحميل أو لم يُحمَّل؛
# يُفعَّل في الإنتاج بعد أن يثبت أن preDeploy يشغّل load_course --all، وإلا علّق النسخة الأولى على نشر لم يحمّل بعد.
KNOWLEDGE_HEALTH_STRICT = env_bool("KNOWLEDGE_HEALTH_STRICT", False)
AXES_CLIENT_IP_CALLABLE = "apps.core.client_ip.client_ip"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ar"
LANGUAGES = [("ar", "العربية"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Qatar"
USE_I18N = True
USE_TZ = True

# الملفات الثابتة: Vite يبني إلى frontend_dist بمعرّف محتوى في اسم كل ملف، وWhiteNoise يخدمها مضغوطة.
# لا نستعمل Manifest storage من Django: هو يعيد تسمية ملف الدخول بينما الأجزاء الكسولة تستورد الاسم الأصلي،
# فيُنفَّذ main.ts مرتين ويُركَّب التطبيق مرتين على #app (صفحة فارغة + TypeError nextSibling).
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
_FRONTEND_DIST = BASE_DIR / "frontend_dist"
STATICFILES_DIRS = [_FRONTEND_DIST] if _FRONTEND_DIST.exists() else []  # يغيب قبل أول npm run build
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
_VITE_HASHED = re.compile(r"/assets/[^/]+-[A-Za-z0-9_-]{8}\.[A-Za-z0-9.]+$")


def _immutable_static(path: str, url: str) -> bool:
    """ملفات Vite معرَّفة بالمحتوى → cache-control immutable؛ البقية (admin) بالافتراضي القصير."""
    return bool(_VITE_HASHED.search(url))


WHITENOISE_IMMUTABLE_FILE_TEST = _immutable_static
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DJANGO_VITE = {
    "default": {
        "dev_mode": False,
        "manifest_path": BASE_DIR / "frontend_dist" / ".vite" / "manifest.json",
        "static_url_prefix": "",
    }
}

# الجلسات والكوكيز: HttpOnly + Secure + SameSite (قاعدة الأمن).
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # Vue يقرأه من الكوكي لإرسال X-CSRFToken
SESSION_COOKIE_AGE = 60 * 60 * 8
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
# CSP: الحزم من الأصل نفسه فقط. style-src يسمح بالأنماط المضمّنة لأن KaTeX يولّدها؛ لا سكربت مضمّن في أي قالب.
SECURITY_CSP = env(
    "SECURITY_CSP",
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; "
    "base-uri 'self'; form-action 'self'",
)
SECURITY_PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"

# تحديد المعدل لمسارات التوليد (حساب sympy على عامِلَين): لكل مستخدم، عبر CACHES.
NINJA_DEFAULT_THROTTLE_RATES = {
    "user": env("THROTTLE_USER_RATE", "90/m"),
    "anon": env("THROTTLE_ANON_RATE", "30/m"),
    "auth": None,
}
# تسخين كاش ملامح الصيغ عند الإقلاع، وإلا كلّف أول طلب بعد النشر 650 مللي ثانية.
PAPERS_WARM_CACHE = env_bool("PAPERS_WARM_CACHE", True)

REDIS_URL = env("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }

# عامل المهام الخلفية (Celery، config/celery.py). الوسيط ومخزن النتائج Redis من REDIS_URL. بلا REDIS_URL
# (تطوير محلي واختبار) تُنفَّذ المهمة في مكانها فورًا فلا يلزم وسيط ولا عامل. في الإنتاج لا تُستدعى مهمة من مسار
# الويب قبل قيام خدمة العامل، وإلا بقيت في الطابور؛ CELERY_TASK_ALWAYS_EAGER=1 يعيد التنفيذ الفوري مؤقتًا.
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = REDIS_URL or "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", not REDIS_URL)
CELERY_TASK_EAGER_PROPAGATES = True
# المهمة تُقَرّ بعد إتمامها لا عند استلامها: موت العامل في أثنائها يعيدها إلى الطابور، ولذلك تُكتب idempotent.
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SOFT_TIME_LIMIT = 270
CELERY_TASK_TIME_LIMIT = 300
CELERY_RESULT_EXPIRES = 3600
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = TIME_ZONE

SITE_TITLE = "مولّد أوراق الرياضيات"
SITE_SUBTITLE = "12 علمي وتكنولوجي، الفصل الأول 2026-2027"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}

# تخزين الأصول (مقاطع العروض). local: قرص للتطوير والاختبار. s3: حاوية متوافقة مع S3 (Railway Bucket) في الإنتاج.
ASSETS_STORAGE = env("ASSETS_STORAGE", "local")
ASSETS_LOCAL_ROOT = Path(env("ASSETS_LOCAL_ROOT", str(BASE_DIR / ".assets")))
ASSETS_S3_ENDPOINT = env("ASSETS_S3_ENDPOINT", "")
ASSETS_S3_BUCKET = env("ASSETS_S3_BUCKET", "")
ASSETS_S3_REGION = env("ASSETS_S3_REGION", "auto")
ASSETS_S3_ACCESS_KEY_ID = env("ASSETS_S3_ACCESS_KEY_ID", "")
ASSETS_S3_SECRET_ACCESS_KEY = env("ASSETS_S3_SECRET_ACCESS_KEY", "")
ASSETS_S3_PATH_STYLE = env_bool("ASSETS_S3_PATH_STYLE", False)  # False = عنوان الحاوية في اسم المضيف
ASSET_LINK_TTL = int(env("ASSET_LINK_TTL", "300"))  # عمر الرابط الموقّع بالثواني
