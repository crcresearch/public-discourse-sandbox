from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.http import HttpRequest
from public_discourse_sandbox.pds_app.models import UserProfile, Experiment

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
    from public_discourse_sandbox.users.models import User


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def save_user(self, request, user, form, commit=True):
        """
        This is called when saving user via allauth registration.
        We save the user as usual, then create the UserProfile if needed.
        """
        # First save the user using the default adapter
        user = super().save_user(request, user, form, commit=False)
        
        # Get any custom fields from the form
        if hasattr(form, 'cleaned_data'):
            # Get profile-specific fields if they exist
            display_name = form.cleaned_data.get('display_name')
            username = form.cleaned_data.get('username')
            bio = form.cleaned_data.get('bio', '')
            profile_picture = form.cleaned_data.get('profile_picture')
            banner_picture = form.cleaned_data.get('banner_picture')
            
            # Save the user first
            if commit:
                user.save()
            
            # Check for pending invitation in session
            pending_invitation = request.session.get('pending_invitation')
            if pending_invitation:
                try:
                    experiment = Experiment.objects.get(
                        identifier=pending_invitation['experiment_identifier']
                    )
                    # Create the UserProfile
                    UserProfile.objects.create(
                        user=user,
                        experiment=experiment,
                        display_name=display_name,
                        username=username,
                        bio=bio,
                        profile_picture=profile_picture,
                        banner_picture=banner_picture
                    )
                except Experiment.DoesNotExist:
                    pass
        elif commit:
            user.save()
            
        return user


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        data: dict[str, typing.Any],
    ) -> User:
        """
        Populates user information from social provider info.

        See: https://docs.allauth.org/en/latest/socialaccount/advanced.html#creating-and-populating-user-instances
        """
        user = super().populate_user(request, sociallogin, data)
        if not user.name:
            if name := data.get("name"):
                user.name = name
            elif first_name := data.get("first_name"):
                user.name = first_name
                if last_name := data.get("last_name"):
                    user.name += f" {last_name}"
        return user
