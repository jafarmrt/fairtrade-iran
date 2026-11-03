from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.contrib.sitemaps.views import sitemap
from wagtail.documents import urls as wagtaildocs_urls

from core import views as core_views
from core.sitemaps import AllLanguagesSitemap

from search import views as search_views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("i18n/", include("django.conf.urls.i18n")),
    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    path("favicon.ico", core_views.favicon, name="favicon"),
    path("sitemap.xml", sitemap, {"sitemaps": {"pages": AllLanguagesSitemap}}, name="sitemap"),
    path("", include("contact.urls")),
    path("", include("appeals.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += i18n_patterns(
    path("search/", search_views.search, name="search"),
    path("panel/", include("memberpanel.urls")),
    path("", include(wagtail_urls)),
    prefix_default_language=True,
)
