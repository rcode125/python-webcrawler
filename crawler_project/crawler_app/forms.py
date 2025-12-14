from django import forms

class CrawlForm(forms.Form):
    start_url = forms.URLField(label="Start URL")
    max_pages = forms.IntegerField(initial=10, min_value=1, max_value=500)
    delay = forms.FloatField(initial=0.5, min_value=0.0)

from django import forms
from .models import DeleteRequest

class DeleteRequestForm(forms.ModelForm):
    class Meta:
        model = DeleteRequest
        fields = ["request_type", "value"]
        widgets = {
            "request_type": forms.Select(attrs={"class": "form-control"}),
            "value": forms.TextInput(attrs={"class": "form-control", "placeholder": "URL oder Domain"}),
        }
from django import forms
from .models import DeleteRequest

class DeleteRequestForm(forms.ModelForm):
    class Meta:
        model = DeleteRequest
        fields = ["request_type", "value"]
        widgets = {
            "request_type": forms.Select(attrs={"class": "form-control"}),
            "value": forms.TextInput(attrs={"class": "form-control", "placeholder": "URL oder Domain"}),
        }
