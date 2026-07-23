from django.urls import path

from .views import *

urlpatterns = [
    path("photos/", PhotoListView.as_view(), name="photo-list"),
    path("photos/calendar/", PhotoCalendarView.as_view(), name="photo-calendar"),
    path("photos/new/", PhotoCreateView.as_view(), name="photo-create"),
    path("photos/new-multiple/", PhotoCreateMultipleView.as_view(), name="photo-create-multiple"),
    path("photos/<pk>/edit/", PhotoUpdateView.as_view(), name="photo-edit"),
    path("photos/<pk>/delete/", PhotoDeleteView.as_view(), name="photo-delete"),
    path("photos/<pk>/", PhotoDetailView.as_view(), name="photo-detail"),
    path("photos/<pk>/size/<str:size>/", PhotoImageView.as_view(), name="photo-image"),

    path("sizes/", SizeListView.as_view(), name="size-list"),
    path("sizes/new/", SizeCreateView.as_view(), name="size-create"),
    path("sizes/<int:pk>/edit/", SizeUpdateView.as_view(), name="size-edit"),
    path("sizes/<int:pk>/delete/", SizeDeleteView.as_view(), name="size-delete"),

    path("albums/", AlbumListView.as_view(), name="album-list"),
    path("albums/new/", AlbumCreateView.as_view(), name="album-create"),
    path("albums/<pk>/edit/", AlbumUpdateView.as_view(), name="album-edit"),
    path("albums/<pk>/delete/", AlbumDeleteView.as_view(), name="album-delete"),
    path("albums/<pk>/", AlbumDetailView.as_view(), name="album-detail"),

    path("tags/", TagListView.as_view(), name="tag-list"),
    path("tags/<int:pk>/edit/", TagUpdateView.as_view(), name="tag-edit"),
    path("tags/<int:pk>/delete/", TagDeleteView.as_view(), name="tag-delete"),
    path("tags/<int:pk>/", TagDetailView.as_view(), name="tag-detail"),
]
