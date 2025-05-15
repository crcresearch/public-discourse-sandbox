from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import QuerySet
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import UpdateView
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from allauth.account.views import EmailVerificationSentView, SignupView
from django import forms

from public_discourse_sandbox.users.models import User
from public_discourse_sandbox.pds_app.mixins import ExperimentContextMixin
from public_discourse_sandbox.pds_app.models import UserProfile, SocialNetwork, Post, Experiment, ExperimentInvitation
from .forms import CustomSignupForm

User = get_user_model()

class UserDetailView(LoginRequiredMixin, ExperimentContextMixin, DetailView):
    model = User
    slug_field = "id"
    slug_url_kwarg = "id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add the experiment identifier to the context for the template
        if self.experiment:
            context['experiment_identifier'] = self.experiment.identifier
        return context


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self) -> str:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user.get_absolute_url()

    def get_object(self, queryset: QuerySet | None=None) -> User:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self) -> str:
        return reverse("users:detail", kwargs={"pk": self.request.user.pk})


user_redirect_view = UserRedirectView.as_view()


class UserProfileDetailView(LoginRequiredMixin, ExperimentContextMixin, DetailView):
    """
    View for displaying a user's profile within a specific experiment context.
    This view requires both a user ID and an experiment identifier in the URL.
    """
    model = UserProfile
    template_name = 'users/user_profile_detail.html'
    context_object_name = 'viewed_profile'
    
    def get_object(self, queryset=None):
        """
        Get the UserProfile object for the specified user and experiment.
        """
        user_id = self.kwargs.get('pk')
        user = get_object_or_404(User, id=user_id)
        return get_object_or_404(
            UserProfile,
            user=user,
            experiment=self.experiment
        )
        
    def get_context_data(self, **kwargs):
        """
        Add experiment and profile context to template context.
        """
        context = super().get_context_data(**kwargs)
        # The ExperimentContextMixin already adds:
        # - experiment
        # - current_user_profile (the current user's profile in this experiment)
        # - is_moderator (current user's moderator status)
        
        # Add the viewed profile's role information
        context['viewed_profile'] = self.object
        context['is_creator'] = self.object.user == self.experiment.creator

        # Add follower and following counts
        context['follower_count'] = SocialNetwork.objects.filter(target_node=self.object).count()
        context['following_count'] = SocialNetwork.objects.filter(source_node=self.object).count()

        # Add posts by this user (not deleted, ordered by newest first)
        context['user_posts'] = Post.all_objects.filter(user_profile=self.object, is_deleted=False).order_by('-created_date')
        # Annotate each post with comment_count and has_user_voted for template compatibility
        current_user = self.request.user
        for post in context['user_posts']:
            post.comment_count = post.get_comment_count()
            post.has_user_voted = post.vote_set.filter(user_profile__user=current_user).exists()

        # Add whether the current user is following the viewed profile
        current_user_profile = context.get('current_user_profile')
        if current_user_profile:
            context['is_following_viewed_profile'] = SocialNetwork.objects.filter(source_node=current_user_profile, target_node=self.object).exists()
        else:
            context['is_following_viewed_profile'] = False
        
        # Followers: UserProfiles that follow this profile
        follower_links = SocialNetwork.objects.filter(target_node=self.object)
        context['followers'] = UserProfile.objects.filter(id__in=follower_links.values_list('source_node', flat=True))

        # Following: UserProfiles that this profile follows
        following_links = SocialNetwork.objects.filter(source_node=self.object)
        context['following'] = UserProfile.objects.filter(id__in=following_links.values_list('target_node', flat=True))
        
        return context

user_profile_detail_view = UserProfileDetailView.as_view()


@method_decorator(require_POST, name='dispatch')
class UpdateProfileView(LoginRequiredMixin, ExperimentContextMixin, View):
    """
    View for handling profile updates via AJAX.
    """
    def post(self, request, *args, **kwargs):
        try:
            user_profile = request.user.userprofile_set.get(experiment=self.experiment)
            
            # Update profile fields
            if 'display_name' in request.POST:
                user_profile.display_name = request.POST['display_name']
            if 'username' in request.POST:
                # Check if username is already taken in this experiment
                if UserProfile.objects.filter(
                    experiment=self.experiment,
                    username=request.POST['username']
                ).exclude(id=user_profile.id).exists():
                    return JsonResponse({
                        'success': False,
                        'error': 'This username is already taken in this experiment'
                    }, status=400)
                user_profile.username = request.POST['username']
            if 'bio' in request.POST:
                user_profile.bio = request.POST['bio']
            
            # Handle profile picture
            if 'profile_picture' in request.FILES:
                user_profile.profile_picture = request.FILES['profile_picture']
            
            # Handle banner picture
            if 'banner_picture' in request.FILES:
                user_profile.banner_picture = request.FILES['banner_picture']
            
            user_profile.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Profile updated successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

update_profile_view = UpdateProfileView.as_view()

class CustomSignupView(SignupView):
    """
    Custom signup view that uses our form with profile fields.
    If accessed without experiment parameter, uses default experiment "00000".
    Email parameter is optional for initial signup from landing page.
    """
    form_class = CustomSignupForm
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Get experiment and email from URL parameters or POST data
        experiment_identifier = self.request.GET.get('experiment') or self.request.POST.get('experiment') or "00000"
        email = self.request.GET.get('email') or self.request.POST.get('email')
        
        try:
            experiment = Experiment.objects.get(identifier=experiment_identifier)
            kwargs['experiment'] = experiment
            
            # If email is provided, check for invitation
            if email:
                try:
                    invitation = ExperimentInvitation.objects.get(
                        experiment=experiment,
                        email=email,
                        is_accepted=False,
                        is_deleted=False
                    )
                    kwargs['initial'] = {'email': email}
                except ExperimentInvitation.DoesNotExist:
                    pass
        except Experiment.DoesNotExist:
            # If the specified experiment doesn't exist, try to use the default "00000"
            if experiment_identifier != "00000":
                try:
                    experiment = Experiment.objects.get(identifier="00000")
                    kwargs['experiment'] = experiment
                except Experiment.DoesNotExist:
                    pass
        
        return kwargs
        
    def get(self, request, *args, **kwargs):
        # We no longer redirect, as we always use a fallback experiment
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add experiment (using fallback if not in request) and email to context for hidden fields
        context['experiment'] = self.request.GET.get('experiment') or self.request.POST.get('experiment') or "00000"
        context['email'] = self.request.GET.get('email') or self.request.POST.get('email')
        return context

    def get_success_url(self):
        # After successful signup, redirect to email verification
        return reverse('account_email_verification_sent')
        
    def form_valid(self, form):
        try:
            # Call parent method to save the User
            response = super().form_valid(form)
            
            user = self.user
            experiment = form.experiment
            
            if user and experiment:
                # Check if the user already has a profile for this experiment
                profile, created = UserProfile.objects.get_or_create(
                    user=user,
                    experiment=experiment,
                    defaults={
                        'username': form.cleaned_data.get('user_name'),
                        'display_name': form.cleaned_data.get('display_name'),
                        'bio': form.cleaned_data.get('bio'),
                    }
                )
                
                # Upload profile/banner pictures if provided
                if created:
                    if form.cleaned_data.get('profile_picture'):
                        profile.profile_picture = form.cleaned_data.get('profile_picture')
                    if form.cleaned_data.get('banner_picture'):
                        profile.banner_picture = form.cleaned_data.get('banner_picture')
                    profile.save()
                
                # If there was an invitation, mark it as accepted
                email = form.cleaned_data.get('email')
                if email:
                    try:
                        invitation = ExperimentInvitation.objects.get(
                            experiment=experiment,
                            email=email,
                            is_accepted=False,
                            is_deleted=False
                        )
                        invitation.is_accepted = True
                        invitation.save()
                    except ExperimentInvitation.DoesNotExist:
                        # No invitation found, which is fine for direct signups
                        pass
            
            return response
        except forms.ValidationError as e:
            # Handle validation errors raised by the adapter
            if hasattr(e, 'error_dict'):
                for field, errors in e.error_dict.items():
                    for error in errors:
                        form.add_error(field, error)
            else:
                form.add_error(None, str(e))
            return self.form_invalid(form)
        except Exception as e:
            # If there's an integrity error, add it to the form and re-render
            error_message = str(e)
            if "duplicate key value violates unique constraint" in error_message:
                if "email" in error_message:
                    form.add_error('email', 'This email address is already in use. Please use a different email address or sign in.')
                elif "display_name" in error_message:
                    form.add_error('display_name', 'This display name is already taken. Please choose a different display name.')
                elif "username" in error_message or "user_name" in error_message:
                    form.add_error('user_name', 'This username is already taken. Please choose a different username.')
                elif "pds_app_userprofile_username_key" in error_message:
                    form.add_error('user_name', 'This username is already taken. Please choose a different username.')
                else:
                    form.add_error(None, 'A field value must be unique: ' + error_message)
            else:
                form.add_error(None, f"An error occurred: {error_message}")
            return self.form_invalid(form)
            
    def form_invalid(self, form):
        """
        Called if the form is invalid. Re-renders the context data with the
        data-filled form and errors.
        """
        # Ensure experiment and email are still in context for hidden fields
        context = self.get_context_data(form=form)
        context['experiment'] = self.request.GET.get('experiment') or self.request.POST.get('experiment') or "00000"
        context['email'] = self.request.GET.get('email') or self.request.POST.get('email')
        
        return self.render_to_response(context)


class CustomEmailVerificationSentView(EmailVerificationSentView):
    """
    Custom view to handle email verification and redirect to create profile
    if there's a pending invitation.
    """
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        
        # Check if there's a pending invitation
        pending_invitation = request.session.get('pending_invitation')
        if pending_invitation:
            # Clear the session data
            del request.session['pending_invitation']
            
            # Redirect to create profile
            return redirect('create_profile', 
                          experiment_identifier=pending_invitation['experiment_identifier'])
        
        return response
