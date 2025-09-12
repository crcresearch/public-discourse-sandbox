from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django.contrib.auth import forms as admin_forms
from django.forms import EmailField
from django.utils.translation import gettext_lazy as _
from django import forms

from .models import User
from public_discourse_sandbox.pds_app.models import (
    UserProfile,
    Experiment,
    ExperimentInvitation,
)


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
        fields = ["display_name", "username", "bio"]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }


class CustomSignupForm(SignupForm):
    """
    Custom signup form that includes profile fields for UserProfile.
    'user_name' is used instead of 'username' to avoid conflict with the User model.
    """

    display_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    user_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    bio = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    profile_picture = forms.ImageField(
        required=False, widget=forms.FileInput(attrs={"class": "form-control"})
    )
    banner_picture = forms.ImageField(
        required=False, widget=forms.FileInput(attrs={"class": "form-control"})
    )
    # Hidden fields for experiment and email
    experiment = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,  # Make optional for rendering
    )

    def __init__(self, *args, **kwargs):
        self.experiment = kwargs.pop("experiment", None)
        super().__init__(*args, **kwargs)

        # Apply styling to email field
        self.fields["email"].widget.attrs["class"] = "form-control"

        if self.experiment:
            # Set experiment field value
            self.fields["experiment"].initial = self.experiment.identifier

            # If we have an email in initial data, make it readonly
            if "initial" in kwargs and kwargs["initial"].get("email"):
                self.fields["email"].widget.attrs["readonly"] = True

    def clean_email(self):
        """
        Validate that the email is unique across all users
        """
        email = self.cleaned_data.get("email")
        if email:
            from django.contrib.auth import get_user_model

            User = get_user_model()

            # Check if a user with this email already exists
            if User.objects.filter(email__iexact=email).exists():
                raise forms.ValidationError("A user with this email already exists.")

        return email

    def clean(self):
        cleaned_data = super().clean()

        # Get experiment from either the form field or the instance variable
        experiment_id = (
            cleaned_data.get("experiment")
            or (self.experiment.identifier if self.experiment else None)
            or "00000"
        )

        # Use default experiment if none provided
        if not experiment_id:
            experiment_id = "00000"

        # If we don't already have an experiment instance, try to get it
        if not self.experiment and experiment_id:
            try:
                self.experiment = Experiment.objects.get(identifier=experiment_id)
            except Experiment.DoesNotExist:
                # For the default experiment, we should ensure it exists
                if experiment_id == "00000":
                    raise forms.ValidationError(
                        'Default experiment "00000" not found in database'
                    )
                else:
                    raise forms.ValidationError("Invalid experiment identifier")

        # Validate username uniqueness
        if self.experiment:
            user_name = cleaned_data.get("user_name")

            if (
                user_name
                and UserProfile.objects.filter(
                    experiment=self.experiment,
                    username__iexact=user_name,  # Case-insensitive check
                ).exists()
            ):
                self.add_error(
                    "user_name", "This username is already taken in this experiment."
                )

        return cleaned_data
