import django_tables2 as tables
from .models import *

# Include CSS Classes: pagination

class PhotoTable(tables.Table):
    id = tables.Column(linkify=True)
    thumbnail = tables.TemplateColumn(
        template_name="core/partials/photo_small_thumbnail.html",
        verbose_name="Thumbnail",
        orderable=False,
    )
    title = tables.Column(linkify=True)
    description = tables.Column(attrs={
        "td": {"class": "hidden md:table-cell"},
        "th": {"class": "hidden md:table-cell"}
    })
    publish_date = tables.Column()
    published = tables.BooleanColumn()

    def render_description(self, value):
        # Limit to 240 characters and add ellipsis if longer
        if len(value) > 240:
            return value[:240] + "..."
        return value

    class Meta:
        model = Photo
        fields = ("id", "thumbnail", "title", "description", "publish_date", "published")
        order_by = ("-publish_date",)


class SizeTable(tables.Table):
    slug = tables.Column()
    comment = tables.Column()
    max_dimension = tables.Column()
    square_crop = tables.BooleanColumn()

    edit = tables.TemplateColumn(
        template_name="core/partials/size_table_edit_button.html",
        verbose_name="Edit",
        orderable=False
    )

    delete = tables.TemplateColumn(
        template_name="core/partials/size_table_delete_button.html",
        verbose_name="Delete",
        orderable=False
    )

    class Meta:
        model = Size
        fields = ("slug", "comment", "max_dimension", "square_crop", "public")


class AlbumTable(tables.Table):
    title = tables.Column(linkify=True)

    class Meta:
        model = Album
        fields = ("title", "slug", "short_description")
        order_by = ("title",)


class PhotoListTable(tables.Table):
    class Meta:
        model = Photo
        template_name = "core/partials/photo_table.html"


class TagTable(tables.Table):
    name = tables.Column(linkify=True)
    photo_count = tables.Column(verbose_name="Photos")
    uuid = tables.Column(attrs={
        "td": {"class": "font-mono"}
    })

    class Meta:
        model = Tag
        fields = ("name", "photo_count", "uuid")
        order_by = ("name",)