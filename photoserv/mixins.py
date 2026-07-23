class CRUDGenericMixin:
    """Provides UI flags and model metadata to generic templates."""

    # UI Behavior Flags
    no_object_detail_page = False
    can_directly_create = True
    can_edit = True
    edit_disclaimer = None

    def get_model(self):
        """Helper to get model class whether view uses self.model or self.get_queryset()"""
        if getattr(self, "model", None):
            return self.model
        if hasattr(self, "get_queryset"):
            return self.get_queryset().model
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model = self.get_model()

        if model:
            opts = model._meta
            context.update({
                "object_type_name": opts.verbose_name.title(),
                "object_type_name_plural": opts.verbose_name_plural.title(),
                "object_url_name_slug": opts.model_name,
            })

        context.update({
            "no_object_detail_page": self.no_object_detail_page,
            "can_directly_create": self.can_directly_create,
            "can_edit": self.can_edit,
            "edit_disclaimer": self.edit_disclaimer,
        })
        return context