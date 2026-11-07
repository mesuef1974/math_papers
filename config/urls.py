"""المسارات: API تحت /api/، الصحة تحت /health/، وكل ما عدا ذلك يذهب إلى واجهة Vue (SPA)."""

from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path

from apps.core.api import api
from apps.core.views import health, spa
from apps.papers.api import router as papers_router

api.add_router("", papers_router)

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/", api.urls),
    path("health/", health, name="health"),
    re_path(r"^(?!api/|static/|media/).*$", spa, name="spa"),
]
