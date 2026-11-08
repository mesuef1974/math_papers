from django.apps import AppConfig
from django.conf import settings


class PapersConfig(AppConfig):
    name = "apps.papers"
    verbose_name = "الأوراق"

    def ready(self) -> None:
        # ملامح الصيغ تُحسب من عينات ثابتة (650 مللي ثانية لكل الدروس)؛ تسخينها هنا بدل أول طلب بعد النشر.
        if getattr(settings, "PAPERS_WARM_CACHE", True):
            from .domain.generators import warm_profiles

            warm_profiles()
