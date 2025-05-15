from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django.contrib.auth import forms as admin_forms
from django.forms import EmailField
from django.utils.translation import gettext_lazy as _
from django import forms

from .models import User
from public_discourse_sandbox.pds_app.models import UserProfile, Experiment, ExperimentInvitation


class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):  # type: ignore[name-defined]
        model = User
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.UserCreationForm):
    """
    Form for User Creation in the Admin Area.
    To change user signup, see UserSignupForm and UserSocialSignupForm.
    """

    class Meta(admin_forms.UserCreationForm.Meta):  # type: ignore[name-defined]
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


class UserSignupForm(SignupForm):
    """
    Form that will be rendered on a user sign up section/screen.
    Default fields will be added automatically.
    Check UserSocialSignupForm for accounts created from social.
    """


class UserSocialSignupForm(SocialSignupForm):
    """
    Renders the form when user has signed up using social accounts.
    Default fields will be added automatically.
    See UserSignupForm otherwise.
    """


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['display_name', 'username', 'bio']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }


class CustomSignupForm(SignupForm):
    """
    Custom signup form that includes profile fields for UserProfile.
    'user_name' is used instead of 'username' to avoid conflict with the User model.
    """
    display_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    user_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    bio = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    profile_picture = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    banner_picture = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    # Hidden fields for experiment and email
    experiment = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        self.experiment = kwargs.pop('experiment', None)
        super().__init__(*args, **kwargs)
        if self.experiment:
            self.fields['email'].widget.attrs['readonly'] = True
            self.fields['email'].widget.attrs['class'] = 'form-control'
            self.fields['experiment'].initial = self.experiment.identifier
    
    def clean(self):
        cleaned_data = super().clean()
        if not self.experiment and cleaned_data.get('experiment'):
            try:
                self.experiment = Experiment.objects.get(identifier=cleaned_data['experiment'])
            except Experiment.DoesNotExist:
                raise forms.ValidationError('Invalid experiment identifier')
        return cleaned_data
    
    def clean_user_name(self):
        user_name = self.cleaned_data.get('user_name')
        if user_name and self.experiment:
            if UserProfile.objects.filter(
                experiment=self.experiment,
                username=user_name
            ).exists():
                raise forms.ValidationError('This username is already taken in this experiment.')
        return user_name
    
    def clean_display_name(self):
        display_name = self.cleaned_data.get('display_name')
        if display_name and self.experiment:
            if UserProfile.objects.filter(
                experiment=self.experiment,
                display_name=display_name
            ).exists():
                raise forms.ValidationError('This display name is already taken in this experiment.')
        return display_name
