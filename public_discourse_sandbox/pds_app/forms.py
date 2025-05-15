from django import forms
from .models import Experiment
from django.contrib.auth import get_user_model
from .models import UserProfile, DigitalTwin

User = get_user_model()

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

class EnrollDigitalTwinForm(forms.Form):
    # User fields
    name = forms.CharField(max_length=255, required=True)
    email = forms.EmailField(required=True)
    # UserProfile fields
    display_name = forms.CharField(max_length=255, required=True)
    username = forms.CharField(max_length=255, required=True)
    bio = forms.CharField(widget=forms.Textarea, required=False)
    banner_picture = forms.ImageField(required=False)
    profile_picture = forms.ImageField(required=False)
    # DigitalTwin fields
    persona = forms.CharField(widget=forms.Textarea, required=False)
    api_token = forms.CharField(max_length=255, required=False)
    llm_url = forms.CharField(max_length=255, required=False)
    llm_model = forms.CharField(max_length=255, required=False)

    def clean_username(self):
        username = self.cleaned_data['username']
        if UserProfile.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_display_name(self):
        display_name = self.cleaned_data['display_name']
        if UserProfile.objects.filter(display_name=display_name).exists():
            raise forms.ValidationError('This display name is already taken.')
        return display_name

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

class UserProfileForm(forms.ModelForm):
    """
    Form for creating and updating user profiles.
    """
    class Meta:
        model = UserProfile
        fields = ['display_name', 'username', 'bio', 'profile_picture', 'banner_picture']
        widgets = {
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
            'banner_picture': forms.FileInput(attrs={'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        self.experiment = kwargs.pop('experiment', None)
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            # Check if username is already taken in this experiment
            existing = UserProfile.objects.filter(
                experiment=self.experiment or self.instance.experiment,
                username=username
            ).exclude(pk=getattr(self.instance, 'pk', None))
            if existing.exists():
                raise forms.ValidationError('This username is already taken in this experiment.')
        return username

    def clean_display_name(self):
        display_name = self.cleaned_data.get('display_name')
        if display_name:
            # Check if display name is already taken in this experiment
            existing = UserProfile.objects.filter(
                experiment=self.experiment or self.instance.experiment,
                display_name=display_name
            ).exclude(pk=getattr(self.instance, 'pk', None))
            if existing.exists():
                raise forms.ValidationError('This display name is already taken in this experiment.')
        return display_name 