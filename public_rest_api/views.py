from rest_framework import viewsets
from core.models import Photo, Size
from .serializers import *
from django.http import FileResponse, Http404
from rest_framework.generics import GenericAPIView
from api_key.authentication import APIKeyAuthentication
from api_key.permissions import HasAPIKey
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from .models import *


INCLUDE_SIZES_PARAM = OpenApiParameter(
    name='include_sizes',
    type=OpenApiTypes.BOOL,
    location=OpenApiParameter.QUERY,
    description='Include photo sizes in the response (default: false)',
    required=False,
)

LATITUDE_LOWER_BOUND_PARAM = OpenApiParameter(
    name='latitude_lower_bound',
    type=OpenApiTypes.FLOAT,
    location=OpenApiParameter.QUERY,
    description='Minimum latitude for location filter (requires latitude_upper_bound)',
    required=False,
)

LATITUDE_UPPER_BOUND_PARAM = OpenApiParameter(
    name='latitude_upper_bound',
    type=OpenApiTypes.FLOAT,
    location=OpenApiParameter.QUERY,
    description='Maximum latitude for location filter (requires latitude_lower_bound)',
    required=False,
)

LONGITUDE_LOWER_BOUND_PARAM = OpenApiParameter(
    name='longitude_lower_bound',
    type=OpenApiTypes.FLOAT,
    location=OpenApiParameter.QUERY,
    description='Minimum longitude for location filter (requires longitude_upper_bound)',
    required=False,
)

LONGITUDE_UPPER_BOUND_PARAM = OpenApiParameter(
    name='longitude_upper_bound',
    type=OpenApiTypes.FLOAT,
    location=OpenApiParameter.QUERY,
    description='Maximum longitude for location filter (requires longitude_lower_bound)',
    required=False,
)


class SizeViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    serializer_class = SizeSerializer
    lookup_field = 'slug'
    queryset = Size.objects.filter(public=True)


class PhotoViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    lookup_field = 'uuid'
    queryset = Photo.objects.filter(_published=True)

    def get_serializer_class(self):
        if self.action == 'list':
            return PhotoSummarySerializer
        return PhotoSerializer
    
    def get_queryset(self):
        """
        Filter photos by location bounds if provided.
        """
        queryset = super().get_queryset()
        
        # Get location bound parameters
        lat_lower = self.request.query_params.get('latitude_lower_bound')
        lat_upper = self.request.query_params.get('latitude_upper_bound')
        lon_lower = self.request.query_params.get('longitude_lower_bound')
        lon_upper = self.request.query_params.get('longitude_upper_bound')
        
        # Validate latitude bounds
        if (lat_lower is not None) != (lat_upper is not None):
            # Only one latitude bound provided
            return queryset.none()  # Will trigger validation error in list()
        
        # Validate longitude bounds
        if (lon_lower is not None) != (lon_upper is not None):
            # Only one longitude bound provided
            return queryset.none()  # Will trigger validation error in list()
        
        # Apply latitude filter if both bounds are provided
        if lat_lower is not None and lat_upper is not None:
            try:
                lat_lower = float(lat_lower)
                lat_upper = float(lat_upper)
                queryset = queryset.filter(
                    hide_location=False,
                    latitude__isnull=False,
                    latitude__gte=lat_lower,
                    latitude__lte=lat_upper
                )
            except (ValueError, TypeError):
                return queryset.none()  # Will trigger validation error in list()
        
        # Apply longitude filter if both bounds are provided
        if lon_lower is not None and lon_upper is not None:
            try:
                lon_lower = float(lon_lower)
                lon_upper = float(lon_upper)
                queryset = queryset.filter(
                    hide_location=False,
                    longitude__isnull=False,
                    longitude__gte=lon_lower,
                    longitude__lte=lon_upper
                )
            except (ValueError, TypeError):
                return queryset.none()  # Will trigger validation error in list()
        
        return queryset
    
    @extend_schema(
        parameters=[
            INCLUDE_SIZES_PARAM,
            LATITUDE_LOWER_BOUND_PARAM,
            LATITUDE_UPPER_BOUND_PARAM,
            LONGITUDE_LOWER_BOUND_PARAM,
            LONGITUDE_UPPER_BOUND_PARAM,
        ],
        responses={200: PhotoSummarySerializer},
    )
    def list(self, request, *args, **kwargs):
        """
        List public photos.
        Optionally include sizes with ?include_sizes=true.
        Optionally filter by location bounds (both lower and upper bounds required for each dimension).
        """
        # Validate location parameters
        lat_lower = request.query_params.get('latitude_lower_bound')
        lat_upper = request.query_params.get('latitude_upper_bound')
        lon_lower = request.query_params.get('longitude_lower_bound')
        lon_upper = request.query_params.get('longitude_upper_bound')
        
        # Check for incomplete latitude bounds
        if (lat_lower is not None) != (lat_upper is not None):
            return Response(
                {"error": "Both latitude_lower_bound and latitude_upper_bound must be provided together."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for incomplete longitude bounds
        if (lon_lower is not None) != (lon_upper is not None):
            return Response(
                {"error": "Both longitude_lower_bound and longitude_upper_bound must be provided together."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate numeric values
        try:
            if lat_lower is not None:
                float(lat_lower)
                float(lat_upper)
            if lon_lower is not None:
                float(lon_lower)
                float(lon_upper)
        except (ValueError, TypeError):
            return Response(
                {"error": "Location bounds must be valid numeric values."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().list(request, *args, **kwargs)


class PhotoImageAPIView(GenericAPIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    queryset = Photo.objects.filter(_published=True)
    lookup_field = "uuid"

    def get(self, request, uuid, size, *args, **kwargs):
        photo = self.get_object()  # GenericAPIView uses queryset + lookup_field
        photo_size = photo.get_size(size)

        if not photo_size or not hasattr(photo_size.image, "open") or not photo_size.size.public:
            raise Http404("Requested size not found.")

        return FileResponse(photo_size.image.open("rb"), content_type="image/jpeg")


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    lookup_field = 'uuid'
    queryset = Tag.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return TagSummarySerializer
        return TagSerializer

    @extend_schema(
        parameters=[INCLUDE_SIZES_PARAM],
        responses={200: TagSerializer},
        description="Retrieve a tag and its associated photos."
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Get a tag by UUID.
        """
        return super().retrieve(request, *args, **kwargs)


class AlbumViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    lookup_field = 'uuid'
    queryset = Album.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return AlbumSummarySerializer
        return AlbumSerializer

    @extend_schema(
        parameters=[INCLUDE_SIZES_PARAM],
        responses={200: AlbumSerializer},
        description="Retrieve an album including metadata, children, and photos."
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Get an album by UUID.
        """
        return super().retrieve(request, *args, **kwargs)


class SiteHealthAPIView(GenericAPIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    serializer_class = SiteHealthSerializer

    def get(self, request, *args, **kwargs):
        from core.models import Photo, PhotoSize

        total_photos = Photo.objects.count()
        total_sizes = Size.objects.count()

        expected_sizes = total_photos * total_sizes
        actual_sizes = PhotoSize.objects.count()
        pending_sizes = expected_sizes - actual_sizes

        photos_with_all_sizes = (
            Photo.objects.annotate(size_count=models.Count("sizes"))
            .filter(size_count=total_sizes)
            .count()
        )

        photos_pending_sizes = total_photos - photos_with_all_sizes
        pending_metadata = Photo.objects.filter(metadata__isnull=True).count()

        site_health = SiteHealth(
            total_photos=total_photos,
            photos_pending_sizes=photos_pending_sizes,
            pending_sizes=pending_sizes,
            pending_metadata=pending_metadata,
        )

        serializer = SiteHealthSerializer(site_health)
        return Response(serializer.data)
