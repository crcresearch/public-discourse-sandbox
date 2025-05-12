from django import forms
from .models import Experiment

class PostForm(forms.Form):
    """Form for creating a new post."""
    content = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'class': 'compose-input',
                'name': 'post_content',
                'placeholder': 'Share your thoughts...',
                'maxlength': '500',
                'required': True,
                'rows': '3',
            }
        ),
        required=True,
    )

    class Media:
        css = {
            'all': ('css/main_dps.css',)
        }

class ExperimentForm(forms.ModelForm):
    """
    Form for creating and editing experiments.
    """
    class Meta:
        model = Experiment
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter experiment name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter experiment description', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add help text
        self.fields['name'].help_text = 'A descriptive name for your experiment'
        self.fields['description'].help_text = 'Detailed description of your experiment' 