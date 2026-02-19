import django_filters
from django import forms
from django_filters.widgets import RangeWidget
from .models import Photo, PhotoMetadata, Album, Tag
from .widgets import CrispyRangeWidget, CrispyDateRangeWidget, CrispyDateTimeRangeWidget, CrispyShutterSpeedRangeWidget
from .fields import ShutterSpeedRangeField


class ShutterSpeedRangeFilter(django_filters.RangeFilter):
    """
    Custom RangeFilter for shutter speed that uses ShutterSpeedRangeField 
    to accept both decimal and fractional notation.
    """
    field_class = ShutterSpeedRangeField


class PhotoFilter(django_filters.FilterSet):
    """
    Comprehensive filter for Photo model including metadata fields.
    Supports filtering by title, slug, description, publish date, metadata fields,
    albums, and tags.
    """
    
    # Basic Photo fields - case-insensitive search
    title = django_filters.CharFilter(
        field_name='title',
        lookup_expr='icontains',
        label='Title'
    )
    
    slug = django_filters.CharFilter(
        field_name='slug',
        lookup_expr='icontains',
        label='Slug'
    )
    
    description = django_filters.CharFilter(
        field_name='description',
        lookup_expr='icontains',
        label='Description'
    )
    
    # Publish date filters
    publish_date = django_filters.DateFromToRangeFilter(
        field_name='publish_date',
        label='Publish date',
        widget=CrispyDateRangeWidget()
    )
    
    # Album and Tag filters (many-to-many)
    albums = django_filters.ModelMultipleChoiceFilter(
        field_name='albums',
        queryset=Album.objects.all(),
        label='Albums',
        widget=forms.CheckboxSelectMultiple
    )
    
    tags = django_filters.ModelMultipleChoiceFilter(
        field_name='tags',
        queryset=Tag.objects.all(),
        label='Tags',
        widget=forms.CheckboxSelectMultiple
    )
    
    # PhotoMetadata fields - Datetime
    capture_date = django_filters.DateTimeFromToRangeFilter(
        field_name='metadata__capture_date',
        label='Capture date',
        widget=CrispyDateRangeWidget()
    )
    
    # PhotoMetadata fields - Numeric (rating)
    rating = django_filters.RangeFilter(
        field_name='metadata__rating',
        label='Rating',
        widget=CrispyRangeWidget(attrs={'type': 'number', 'step': '1'})
    )
    
    # PhotoMetadata fields - CharFields with case-insensitive search
    camera_make = django_filters.CharFilter(
        field_name='metadata__camera_make',
        lookup_expr='icontains',
        label='Camera make'
    )
    
    camera_model = django_filters.CharFilter(
        field_name='metadata__camera_model',
        lookup_expr='icontains',
        label='Camera model'
    )
    
    lens_model = django_filters.CharFilter(
        field_name='metadata__lens_model',
        lookup_expr='icontains',
        label='Lens model'
    )
    
    exposure_program = django_filters.CharFilter(
        field_name='metadata__exposure_program',
        lookup_expr='icontains',
        label='Exposure program (PASM)'
    )
    
    flash = django_filters.CharFilter(
        field_name='metadata__flash',
        lookup_expr='icontains',
        label='Flash'
    )
    
    copyright = django_filters.CharFilter(
        field_name='metadata__copyright',
        lookup_expr='icontains',
        label='Copyright'
    )
    
    # PhotoMetadata fields - Numeric (focal_length)
    focal_length = django_filters.RangeFilter(
        field_name='metadata__focal_length',
        label='Focal length (real)',
        widget=CrispyRangeWidget(attrs={'type': 'number', 'step': '0.1'})
    )
    
    # PhotoMetadata fields - Numeric (focal_length_35mm)
    focal_length_35mm = django_filters.RangeFilter(
        field_name='metadata__focal_length_35mm',
        label='Focal length (35mm equiv.)',
        widget=CrispyRangeWidget(attrs={'type': 'number', 'step': '0.1'})
    )
    
    # PhotoMetadata fields - Numeric (aperture)
    aperture = django_filters.RangeFilter(
        field_name='metadata__aperture',
        label='Aperture',
        widget=CrispyRangeWidget(attrs={'type': 'number', 'step': '0.1'})
    )
    
    # PhotoMetadata fields - Numeric (shutter_speed)
    shutter_speed = ShutterSpeedRangeFilter(
        field_name='metadata__shutter_speed',
        label='Shutter speed',
        widget=CrispyShutterSpeedRangeWidget()
    )
    
    # PhotoMetadata fields - Numeric (iso)
    iso = django_filters.RangeFilter(
        field_name='metadata__iso',
        label='ISO',
        widget=CrispyRangeWidget(attrs={'type': 'number'})
    )
    
    # PhotoMetadata fields - Numeric (exposure_compensation)
    exposure_compensation = django_filters.RangeFilter(
        field_name='metadata__exposure_compensation',
        label='Exposure compensation',
        widget=CrispyRangeWidget(attrs={'type': 'number', 'step': '0.1'})
    )
    
    class Meta:
        model = Photo
        fields = []  # We define all fields explicitly above
