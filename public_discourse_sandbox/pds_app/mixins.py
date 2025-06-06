from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from .models import Experiment, UserProfile, ExperimentInvitation

class ExperimentContextMixin:
    """
    A Django mixin that handles experiment context and access control for multi-tenant views.
    
    This mixin is central to the application's multi-tenant architecture, where each experiment
    acts as a tenant. It manages experiment context, verifies user access, and handles
    redirections when necessary.

    Key Features:
    - Automatically determines the current experiment from URL or user's last_accessed
    - Verifies user access to the experiment
    - Handles redirections to experiment-specific URLs
    - Updates user's last_accessed experiment
    - Adds experiment and user_profile to template context

    Usage:
        class MyView(ExperimentContextMixin, View):
            def get(self, request, *args, **kwargs):
                # self.experiment and self.user_profile are available here
                pass

    URL Pattern Requirements:
    - For experiment-specific views, include 'experiment_identifier' in URL pattern
    - For non-experiment views, the mixin will use last_accessed experiment

    Template Context:
    - experiment: The current Experiment instance
    - user_profile: The UserProfile instance for current user in this experiment
    - experiment_identifier: The identifier of the current experiment

    Redirection Behavior:
    1. If URL has experiment_identifier:
       - Valid identifier: Uses that experiment
       - Invalid identifier: Redirects to last_accessed experiment
    2. If URL has no experiment_identifier:
       - Uses last_accessed experiment and redirects to experiment-specific URL
    3. If no last_accessed experiment:
       - Uses first available experiment and redirects

    Permission Handling:
    - Raises PermissionDenied if:
      - User has no access to any experiments
      - User has no profile in the selected experiment

    Example URL Patterns:
        path("<str:experiment_identifier>/home/", HomeView.as_view(), name="home_with_experiment")
        path("home/", HomeView.as_view(), name="home")  # Will use last_accessed
    """
    def setup(self, request, *args, **kwargs):
        """
        Initialize experiment context and verify access.
        
        This method is called before the view's dispatch method. It:
        1. Determines the current experiment
        2. Verifies user access
        3. Sets up redirection if needed
        4. Updates last_accessed experiment
        
        Args:
            request: The current request object
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments, including experiment_identifier if present
        """
        super().setup(request, *args, **kwargs)
        self.experiment = None
        self.should_redirect = False
        self.user_profile = None
        self.redirect_to_landing = False
        
        if request.user.is_authenticated:
            def get_valid_experiment(exp):
                if exp and not exp.is_deleted:
                    return exp
                return None

            # Try to get experiment from URL
            if 'experiment_identifier' in kwargs:
                try:
                    self.experiment = Experiment.objects.get(identifier=kwargs['experiment_identifier'])
                except Experiment.DoesNotExist:
                    self.experiment = None

            # If not found, try last_accessed (but only if not deleted)
            if not self.experiment:
                self.experiment = get_valid_experiment(getattr(request.user, 'last_accessed', None))
                if self.experiment:
                    self.should_redirect = True

            # If still not found, try first available experiment
            if not self.experiment:
                user_profile = request.user.userprofile_set.filter(experiment__is_deleted=False).first()
                if user_profile:
                    self.experiment = user_profile.experiment
                    self.should_redirect = True

            # If still not found, set redirect flag
            if not self.experiment:
                self.redirect_to_landing = True
                return

            # Get user's profile for this experiment
            self.user_profile = request.user.userprofile_set.filter(experiment=self.experiment).first()

            # Update user's last_accessed experiment if needed
            if request.user.last_accessed != self.experiment:
                request.user.last_accessed = self.experiment
                request.user.save()

    def is_moderator(self, user, experiment):
        """
        Check if a user has moderator permissions for an experiment.
        Uses the UserProfile's is_experiment_moderator method.
        """
        if not user.is_authenticated:
            return False
            
        user_profile = user.userprofile_set.filter(experiment=experiment).first()
        if not user_profile:
            return False
            
        return user_profile.is_experiment_moderator()
        
    def check_moderator_permission(self):
        """
        Check if the current user has moderator permissions.
        Raises PermissionDenied if not a moderator.
        """
        if not self.is_moderator(self.request.user, self.experiment):
            raise PermissionDenied("You do not have moderator permissions for this experiment.")
            
    def get_context_data(self, **kwargs):
        """
        Add experiment and moderator context to template context.
        """
        context = super().get_context_data(**kwargs)
        if self.experiment:
            context['experiment'] = self.experiment
            context['current_user_profile'] = self.user_profile
            context['is_moderator'] = self.is_moderator(self.request.user, self.experiment)
        return context

    def dispatch(self, request, *args, **kwargs):
        """
        Handle request dispatch and redirection.
        
        This method:
        1. Calls the parent dispatch method
        2. Handles redirection to experiment-specific URLs if needed
        3. Returns the appropriate response
        
        Args:
            request: The current request object
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            HttpResponse: The response to send to the client
        """
        # Handle redirect if setup flagged it
        if getattr(self, 'redirect_to_landing', False):
            return redirect("/")
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

class ModeratorPermissionMixin:
    """
    Mixin that provides moderator permission checking for views.
    A user is considered a moderator if they:
    1. Own the experiment (are the creator)
    2. Are a collaborator
    3. Have the is_moderator flag set
    """
    def is_moderator(self, user, experiment):
        """
        Check if a user has moderator permissions for an experiment.
        """
        if not user.is_authenticated:
            return False
            
        user_profile = user.userprofile_set.filter(experiment=experiment).first()
        if not user_profile:
            return False
            
        return (
            experiment.creator == user or  # User owns the experiment
            user_profile.is_collaborator or  # User is a collaborator
            user_profile.is_moderator  # User has moderator flag
        )
        
    def check_moderator_permission(self):
        """
        Check if the current user has moderator permissions.
        Raises PermissionDenied if not a moderator.
        """
        if not self.is_moderator(self.request.user, self.experiment):
            raise PermissionDenied("You do not have moderator permissions for this experiment.")
            
    def get_context_data(self, **kwargs):
        """
        Add is_moderator to template context.
        """
        context = super().get_context_data(**kwargs)
        context['is_moderator'] = self.is_moderator(self.request.user, self.experiment)
        return context 

class ProfileRequiredMixin:
    """
    Mixin that redirects users to create their profile if they don't have one.
    Handles both experiment creators and invited users.
    Should be used after ExperimentContextMixin in the inheritance chain.
    """
    def dispatch(self, request, *args, **kwargs):
        # Skip if we're already on the create profile page
        if request.resolver_match.url_name == 'create_profile':
            return super().dispatch(request, *args, **kwargs)
            
        # Check if user needs a profile
        needs_profile = (
            # Creator without profile
            (self.experiment.creator == request.user and not self.user_profile) or
            # Invited user without profile
            (not self.user_profile and 
             ExperimentInvitation.objects.filter(
                 experiment=self.experiment,
                 email=request.user.email,
                 is_deleted=False
             ).exists())
        )
        
        if needs_profile:
            return redirect('create_profile', experiment_identifier=self.experiment.identifier)
            
        return super().dispatch(request, *args, **kwargs) 