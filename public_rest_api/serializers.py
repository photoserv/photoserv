from core.models import Photo, Size, Album, Tag, PhotoMetadata, PhotoTag, PhotoSize
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field


class PhotoSizeSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(source='size.uuid', read_only=True)
    slug = serializers.CharField(source='size.slug', read_only=True)

    class Meta:
        model = PhotoSize
        fields = ["uuid", "slug", "height", "width", "md5"]


class PhotoMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhotoMetadata
        exclude = ['uuid', 'id', 'photo', "raw_latitude", "raw_longitude"]


class AlbumSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Album
        fields = ["uuid", "slug", "title", "short_description"]


class TagSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["uuid", "name"]


class PhotoSummarySerializer(serializers.ModelSerializer):
    sizes = serializers.SerializerMethodField()

    @extend_schema_field(PhotoSizeSerializer(many=True))
    def get_sizes(self, obj):
        request = self.context.get("request")

        include_sizes = False
        if request:
            include_sizes = request.query_params.get("include_sizes", "").lower() in ["1", "true", "yes"]

        if not include_sizes:
            return []

        public_sizes = obj.sizes.filter(size__public=True)
        return PhotoSizeSerializer(public_sizes, many=True).data

    class Meta:
        model = Photo
        fields = ["uuid", "title", "slug", "publish_date", "sizes"]


class AlbumSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()
    parent = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = ["uuid", "title", "slug", "short_description", "description", "sort_method", "sort_descending", "photos", "parent", "children", "custom_attributes", "created_at", "updated_at"]

    @extend_schema_field(PhotoSummarySerializer(many=True))
    def get_photos(self, obj):
        return PhotoSummarySerializer(obj.get_ordered_photos(public_only=True), many=True, context=self.context).data
    
    @extend_schema_field(AlbumSummarySerializer(allow_null=True))
    def get_parent(self, obj):
        if obj.parent:
            return AlbumSummarySerializer(obj.parent).data
        return None
    
    @extend_schema_field(AlbumSummarySerializer(many=True))
    def get_children(self, obj):
        return AlbumSummarySerializer(obj.children.all(), many=True).data


class TagSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ["uuid", "name", "photos"]

    @extend_schema_field(PhotoSummarySerializer(many=True))
    def get_photos(self, obj):
        return PhotoSummarySerializer(obj.photos.filter(_published=True), many=True, context=self.context).data


class LocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class PhotoSerializer(serializers.ModelSerializer):
    metadata = PhotoMetadataSerializer(read_only=True)
    albums = AlbumSummarySerializer(many=True, read_only=True)
    tags = TagSummarySerializer(many=True, read_only=True)
    sizes = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()

    @extend_schema_field(PhotoSizeSerializer(many=True))
    def get_sizes(self, obj):
        public_sizes = obj.sizes.filter(size__public=True)
        return PhotoSizeSerializer(public_sizes, many=True).data
    
    @extend_schema_field(LocationSerializer(allow_null=True))
    def get_location(self, obj):
        if obj.hide_location:
            return None
        if obj.latitude is not None and obj.longitude is not None:
            return {
                "latitude": obj.latitude,
                "longitude": obj.longitude
            }
        return None

    class Meta:
        model = Photo
        fields = [
            "uuid", "title", "slug", "description", "custom_attributes", "publish_date", "albums", "tags", "metadata", "sizes", "location", "created_at", "updated_at"
        ]


class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = ["uuid", "slug", "max_dimension", "square_crop", "created_at", "updated_at"]


class SiteHealthSerializer(serializers.Serializer):
    total_photos = serializers.IntegerField()
    photos_pending_sizes = serializers.IntegerField()
    pending_sizes = serializers.IntegerField()
    pending_metadata = serializers.IntegerField()
