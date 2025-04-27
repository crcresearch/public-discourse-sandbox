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
    If an invalid experiment identifier is provided, redirects to the user's last_accessed experiment.
    """
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.experiment = None
        self.should_redirect = False
        self.user_profile = None
        
        if request.user.is_authenticated:
            # First try to get experiment from URL
            if 'experiment_identifier' in kwargs:
                try:
                    self.experiment = Experiment.objects.get(identifier=kwargs['experiment_identifier'])
                except Experiment.DoesNotExist:
                    # If experiment doesn't exist, use last_accessed
                    if hasattr(request.user, 'last_accessed') and request.user.last_accessed:
                        self.experiment = request.user.last_accessed
                        self.should_redirect = True
                    else:
                        # If no last_accessed, try to get the user's first available experiment
                        user_profile = request.user.userprofile_set.first()
                        if user_profile:
                            self.experiment = user_profile.experiment
                            self.should_redirect = True
                        else:
                            raise PermissionDenied("You do not have access to any experiments")
            # If no identifier in URL, try to get from user's last_accessed
            elif hasattr(request.user, 'last_accessed') and request.user.last_accessed:
                self.experiment = request.user.last_accessed
                self.should_redirect = True
            else:
                # If no experiment found, try to get the user's first available experiment
                user_profile = request.user.userprofile_set.first()
                if user_profile:
                    self.experiment = user_profile.experiment
                    self.should_redirect = True
                else:
                    raise PermissionDenied("You do not have access to any experiments")
            
            # Verify user has access to this experiment and get their profile for this experiment
            if self.experiment:
                self.user_profile = request.user.userprofile_set.filter(experiment=self.experiment).first()
                if not self.user_profile:
                    raise PermissionDenied("You do not have a profile in this experiment")
                
                # Update user's last_accessed experiment
                request.user.last_accessed = self.experiment
                request.user.save()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.experiment:
            context['experiment'] = self.experiment
            context['user_profile'] = self.user_profile
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        
        # If we should redirect and we have an experiment, redirect to the URL with the identifier
        if self.should_redirect and self.experiment:
            # Get the current URL name and namespace
            current_url_name = request.resolver_match.url_name
            current_namespace = request.resolver_match.namespace
            
            # Map the current URL name to its "with_experiment" version
            url_name_mapping = {
                'home': 'home_with_experiment',
                'explore': 'explore_with_experiment',
                'create_comment': 'create_comment_with_experiment',
                'get_replies': 'get_replies_with_experiment',
                'delete_post': 'delete_post_with_experiment',
                'ban_user': 'ban_user_with_experiment',
                'unban_user': 'unban_user_with_experiment',
                'detail': 'detail_with_experiment',
                'about': 'about_with_experiment',
            }
            
            # Get the new URL name, defaulting to the current one if not in mapping
            new_url_name = url_name_mapping.get(current_url_name, current_url_name)
            
            # Get the URL parameters
            url_kwargs = request.resolver_match.kwargs.copy()
            url_kwargs['experiment_identifier'] = self.experiment.identifier
            
            # If we have a namespace, use it in the reverse call
            if current_namespace:
                new_url_name = f"{current_namespace}:{new_url_name}"
            
            # Redirect to the new URL
            return redirect(reverse(new_url_name, kwargs=url_kwargs))
        
        return response 