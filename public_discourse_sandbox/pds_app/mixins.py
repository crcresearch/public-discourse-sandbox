from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from .models import Experiment, UserProfile

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
        """
        Add experiment context to template context.
        
        This method adds the current experiment and user profiles to the template context,
        making them available in templates.
        
        The user profiles are handled specially to maintain both:
        - current_user_profile: The profile of the currently logged-in user (used in left nav, etc.)
        - user_profile: The profile being viewed (used in profile pages)
        
        Example Use Case:
        - When viewing a user's profile page (e.g., /users/00000/1a8336c2-8573-4310-8dab-cc24e0e8f643/):
          1. UserProfileDetailView gets the requested user's profile and sets it as user_profile
          2. This mixin adds the current user's profile as current_user_profile
          3. Template shows the requested user's profile information
          4. Left nav shows the current user's information
        
        - When viewing the home page:
          1. No view sets user_profile in context
          2. This mixin adds the current user's profile as current_user_profile
          3. Template shows the current user's information
          4. Left nav shows the current user's information
        
        Args:
            **kwargs: Additional context data
            
        Returns:
            dict: Updated context with experiment and user profiles
        """
        context = super().get_context_data(**kwargs)
        if self.experiment:
            context['experiment'] = self.experiment
            # Always add current user's profile as current_user_profile
            context['current_user_profile'] = self.user_profile
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