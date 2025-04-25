from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from .models import Experiment, UserProfile

class ExperimentContextMixin:
    """
    Mixin to handle experiment context in views.
    Adds experiment context to the view and verifies user access.
    If no experiment identifier is provided in the URL, uses the user's last_accessed experiment
    and redirects to the URL with the experiment identifier.
    """
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.experiment = None
        self.should_redirect = False
        
        if request.user.is_authenticated:
            # First try to get experiment from URL
            if 'experiment_identifier' in kwargs:
                self.experiment = get_object_or_404(Experiment, identifier=kwargs['experiment_identifier'])
            # If no identifier in URL, try to get from user's last_accessed
            elif hasattr(request.user, 'last_accessed') and request.user.last_accessed:
                self.experiment = request.user.last_accessed
                self.should_redirect = True
            else:
                # If no experiment found, try to get the user's first available experiment
                try:
                    user_profile = request.user.userprofile
                    self.experiment = user_profile.experiment
                    self.should_redirect = True
                except UserProfile.DoesNotExist:
                    raise PermissionDenied("You do not have access to any experiments")
            
            # Verify user has access to this experiment
            if self.experiment:
                try:
                    user_profile = request.user.userprofile
                    if user_profile.experiment != self.experiment:
                        raise PermissionDenied("You do not have access to this experiment")
                except UserProfile.DoesNotExist:
                    raise PermissionDenied("You do not have a profile in this experiment")
                
                # Update user's last_accessed experiment
                request.user.last_accessed = self.experiment
                request.user.save()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.experiment:
            context['experiment'] = self.experiment
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        
        # If we should redirect and we have an experiment, redirect to the URL with the identifier
        if self.should_redirect and self.experiment:
            # Get the current URL name
            current_url_name = request.resolver_match.url_name
            
            # Map the current URL name to its "with_experiment" version
            url_name_mapping = {
                'home': 'home_with_experiment',
                'explore': 'explore_with_experiment',
                'create_comment': 'create_comment_with_experiment',
                'get_replies': 'get_replies_with_experiment',
                'delete_post': 'delete_post_with_experiment',
                'ban_user': 'ban_user_with_experiment',
                'unban_user': 'unban_user_with_experiment',
            }
            
            # Get the new URL name, defaulting to the current one if not in mapping
            new_url_name = url_name_mapping.get(current_url_name, current_url_name)
            
            # Get the URL parameters
            url_kwargs = request.resolver_match.kwargs.copy()
            url_kwargs['experiment_identifier'] = self.experiment.identifier
            
            # Redirect to the new URL
            return redirect(reverse(new_url_name, kwargs=url_kwargs))
        
        return response 