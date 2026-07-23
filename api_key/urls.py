from django.urls import path

from .views import *

urlpatterns = [
    path("api-keys/", APIKeyListView.as_view(), name="apikey-list"),
    path("api-keys/new/", APIKeyCreateView.as_view(), name="apikey-create"),
    path("api-keys/<pk>/edit/", APIKeyUpdateView.as_view(), name="apikey-edit"),
    path("api-keys/<pk>/delete/", APIKeyDeleteView.as_view(), name="apikey-delete"),
]
