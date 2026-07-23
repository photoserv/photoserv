from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from .models import APIKey


class APIKeyForm(forms.ModelForm):
    expires_on = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Only set initial if the form is not bound and no instance value exists
        if not self.instance.pk and not self.initial.get("expires_on"):
            self.fields["expires_on"].initial = APIKey._meta.get_field("expires_on").get_default()

        self.helper = FormHelper(self)

    class Meta:
        model = APIKey
        fields = ['name', 'is_active', 'write_access', 'expires_on']
