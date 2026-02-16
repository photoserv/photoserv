"""
URL configuration for photoserv project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from core.urls import urlpatterns as core_urls
from public_rest_api.urls import urlpatterns as api_urls
from api_key.urls import urlpatterns as api_key_urls
from iam.urls import urlpatterns as iam_urls
from home.urls import urlpatterns as home_urls
from job_overview.urls import urlpatterns as job_overview_urls
from integration.urls import urlpatterns as integration_urls
from drf_spectacular.views import SpectacularSwaggerView, SpectacularJSONAPIView
from errorhtml import views as error_views
from .settings import DEBUG

handler400 = error_views.error_400
handler403 = error_views.error_403
handler404 = error_views.error_404
handler500 = error_views.error_500

urlpatterns = [
    path("api/", include(api_urls)),
    path("", include(core_urls)),
    path("", include(api_key_urls)),
    path("", include(iam_urls)),
    path("", include(home_urls)),
    path("", include(job_overview_urls)),
    path("integrations/", include(integration_urls)),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="swagger"),
    path("swagger/schema/", SpectacularJSONAPIView.as_view(), name="api-schema"),
]

if DEBUG:
    urlpatterns += path('admin/', admin.site.urls),
