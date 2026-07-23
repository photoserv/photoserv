import django_tables2 as tables
from .models import APIKey


class APIKeyTable(tables.Table):

    edit = tables.TemplateColumn(
        template_name="partials/table_row_edit_button.html",
        verbose_name="Edit",
        orderable=False,
        extra_context = {
            "url_slug": "apikey-edit"
        }
    )

    delete = tables.TemplateColumn(
        template_name="partials/table_row_delete_button.html",
        verbose_name="Delete",
        orderable=False,
        extra_context = {
            "url_slug": "apikey-delete"
        }
    )

    class Meta:
        model = APIKey
        fields = ("id", 'name', 'is_active', 'write_access', "created_at", 'expires_on', "edit", "delete")
        order_by = ("id",)
