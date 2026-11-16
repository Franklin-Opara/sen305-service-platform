from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class AssignmentForm(forms.Form):
    technician = forms.ModelChoiceField(
        queryset=User.objects.filter(is_staff=True, is_active=True),
        empty_label="Select a technician",
    )


class ResolutionForm(forms.Form):
    work_notes = forms.CharField(
        min_length=3,
        widget=forms.Textarea(attrs={"rows": 4}),
    )