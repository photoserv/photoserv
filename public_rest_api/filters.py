import django_filters
from django import forms
from core.models import Photo, Album, Tag
from core.filters import PhotoFilter


class PhotoFilterAPI(PhotoFilter):
    """
    API version of PhotoFilter that uses UUIDs for albums and tags instead of IDs.
    
    This filter inherits all filters from PhotoFilter but overrides the albums
    and tags filters to accept UUIDs instead of primary key IDs.
    """
    
    albums = django_filters.ModelMultipleChoiceFilter(
        field_name='albums__uuid',
        to_field_name='uuid',
        queryset=Album.objects.all(),
        label='Albums'
    )
    tags = django_filters.ModelMultipleChoiceFilter(
        field_name='tags__uuid',
        to_field_name='uuid',
        queryset=Tag.objects.all(),
        label='Tags'
    )
