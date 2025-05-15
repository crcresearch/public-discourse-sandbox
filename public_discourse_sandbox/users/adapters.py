from __future__ import annotations

import typing
from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.http import HttpRequest
from allauth.account.utils import user_email, user_field, user_username
from allauth.utils import valid_email_or_none
from public_discourse_sandbox.pds_app.models import UserProfile, Experiment
from django import forms

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
        try:
            # First save the user using the default adapter
            user = super().save_user(request, user, form, commit=False)
            
            # Get any custom fields from the form
            if hasattr(form, 'cleaned_data'):
                # Get profile-specific fields if they exist
                display_name = form.cleaned_data.get('display_name')
                user_name = form.cleaned_data.get('user_name') or display_name
                bio = form.cleaned_data.get('bio', '')
                profile_picture = form.cleaned_data.get('profile_picture')
                banner_picture = form.cleaned_data.get('banner_picture')
                experiment_id = form.cleaned_data.get('experiment')
                
                # Save the user first
                if commit:
                    try:
                        user.save()
                    except Exception as e:
                        # Handle email uniqueness error
                        if "duplicate key value violates unique constraint" in str(e) and "email" in str(e):
                            form.add_error('email', 'This email address is already in use. Please use a different email address or sign in.')
                            raise forms.ValidationError({
                                'email': ['This email address is already in use.']
                            })
                        raise
                
                # Get experiment from form or form data
                experiment = getattr(form, 'experiment', None)
                if not experiment and experiment_id:
                    try:
                        experiment = Experiment.objects.get(identifier=experiment_id)
                    except Experiment.DoesNotExist:
                        pass
                
                if experiment:
                    try:
                        # Check for existing UserProfile with the same username
                        if user_name:
                            # Check uniqueness only within the experiment - be thorough to catch any issues
                            print(f"DEBUG: Adapter checking if username '{user_name}' exists in experiment {experiment.identifier}")
                            
                            # Check case-sensitive match first
                            existing_profile = UserProfile.objects.filter(
                                experiment=experiment,
                                username=user_name
                            ).first()
                            
                            # Then try case-insensitive if needed
                            if not existing_profile:
                                existing_profile = UserProfile.objects.filter(
                                    experiment=experiment,
                                    username__iexact=user_name
                                ).first()
                            
                            if existing_profile:
                                error_msg = f'This username "{user_name}" is already taken in this experiment. Please choose a different username.'
                                print(f"DEBUG: Adapter found existing profile with username '{existing_profile.username}' - adding error")
                                form.add_error('user_name', error_msg)
                                raise forms.ValidationError({
                                    'user_name': [error_msg]
                                })
                            else:
                                print(f"DEBUG: Adapter confirmed username '{user_name}' is available in experiment {experiment.identifier}")
                        
                        # Create the UserProfile
                        profile = UserProfile.objects.create(
                            user=user,
                            experiment=experiment,
                            display_name=display_name,
                            username=user_name,
                            bio=bio,
                            profile_picture=profile_picture,
                            banner_picture=banner_picture
                        )
                        
                        # Set last_accessed experiment
                        user.last_accessed = experiment
                        user.save()
                    except forms.ValidationError:
                        # Re-raise the validation error to be caught by the form
                        raise
                    except Exception as e:
                        # Convert any other exception to a form validation error
                        error_message = str(e)
                        print(f"DEBUG: Adapter caught exception: {error_message}")
                        
                        if "duplicate key value violates unique constraint" in error_message:
                            if "username" in error_message or "pds_app_userprofile_username" in error_message:
                                print(f"DEBUG: Adapter detected username constraint violation")
                                form.add_error('user_name', 'This username is already taken in this experiment.')
                            elif "pds_app_userprofile_username_experiment_id_key" in error_message:
                                print(f"DEBUG: Adapter detected username+experiment constraint violation")
                                form.add_error('user_name', 'This username is already taken in this experiment.')
                            else:
                                print(f"DEBUG: Adapter detected other constraint violation")
                                form.add_error(None, str(e))
                        else:
                            print(f"DEBUG: Adapter detected non-constraint error")
                            form.add_error(None, str(e))
                        raise forms.ValidationError("Error creating user profile. Please check the form for errors.")
            elif commit:
                user.save()
                
            return user
        except forms.ValidationError:
            # Already added the errors to the form, just re-raise
            raise
        except Exception as e:
            # Handle any other exceptions by adding a form error
            if hasattr(form, 'add_error'):
                form.add_error(None, f"Error creating account: {str(e)}")
            raise forms.ValidationError(f"Error creating account: {str(e)}")


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
