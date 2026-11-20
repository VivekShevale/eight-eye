from django.contrib import admin
from django.urls import include, path

from apps.common.views import HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthView.as_view(), name="health"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/tickets/", include("apps.tickets.urls")),
]

# JSON instead of HTML pages for unknown URLs and crashes outside DRF views (active when DEBUG is false).
handler404 = "apps.common.views.page_not_found"
handler500 = "apps.common.views.server_error"
