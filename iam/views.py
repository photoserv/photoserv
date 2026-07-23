from django.conf import settings
from django.shortcuts import redirect
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django_tables2.views import SingleTableView
from django.contrib.auth import views as auth_views
from django.urls import reverse
from photoserv.mixins import CRUDGenericMixin
from .models import User
from .tables import UserTable
from .forms import UserForm


class LoginView(auth_views.LoginView):
    def dispatch(self, request, *args, **kwargs):
        # Safely fetch settings, default to False if not present
        oidc_enabled = getattr(settings, "OIDC_ENABLED", False)
        simple_auth = getattr(settings, "SIMPLE_AUTH", False)

        # Both disabled -> redirect to /
        if not oidc_enabled and not simple_auth:
            return redirect(reverse("home"))

        # Only OIDC enabled -> redirect to OIDC login
        if oidc_enabled and not simple_auth:
            return redirect(reverse("oidc_authentication_init"))

        # SIMPLE_AUTH true (with or without OIDC) -> default LoginView
        return super().dispatch(request, *args, **kwargs)


class UserMixin(CRUDGenericMixin):
    object_type_name = "User"
    object_type_name_plural = "Users"
    object_url_name_slug = "user"
    edit_disclaimer = "OIDC users will have their properties overwritten upon login."


class UserListView(UserMixin, SingleTableView):
    model = User
    table_class = UserTable
    template_name = "generic_crud_list.html"


class UserDetailView(DetailView):
    model = User


class UserCreateView(UserMixin, CreateView):
    model = User
    form_class = UserForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('user-detail', kwargs={'pk': self.object.pk})


class UserUpdateView(UserMixin, UpdateView):
    model = User
    form_class = UserForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('user-detail', kwargs={'pk': self.object.pk})


class UserDeleteView(DeleteView):
    model = User
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('user-list')
