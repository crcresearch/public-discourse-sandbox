from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from functools import wraps

def check_banned(view_func):
    """
    Decorator to check if a user is banned before allowing access to a view.
    
    This decorator performs several checks in sequence:
    1. Verifies the experiment context (either from URL or user's last_accessed)
    2. Confirms the user has a profile in the experiment
    3. Checks if the user is banned
    
    The decorator handles both API views (returning JSON responses) and regular views
    (raising PermissionDenied exceptions) based on the request type.
    
    Usage:
        For function-based views:
        @check_banned
        def my_view(request, experiment_identifier):
            # Your view code here
            
        For class-based views:
        @method_decorator(check_banned)
        def post(self, request, *args, **kwargs):
            # Your view code here
            
    Parameters:
        view_func: The view function to be decorated
        
    Returns:
        - For API requests (XHR):
            JsonResponse with status 403 and error message if user is banned
            JsonResponse with status 400 if no experiment is selected
            JsonResponse with status 403 if user profile is not found
        - For regular requests:
            PermissionDenied exception with appropriate message
            
    Raises:
        PermissionDenied: If the user is banned, has no experiment selected,
                         or has no profile in the experiment (for non-API requests)
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Get the experiment from the URL parameter or kwargs
        experiment_identifier = kwargs.get('experiment_identifier')
        if not experiment_identifier:
            # If no experiment in URL, try to get it from the user's last_accessed
            experiment = request.user.last_accessed
            if not experiment:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'error',
                        'message': 'No experiment selected'
                    }, status=400)
                raise PermissionDenied("No experiment selected")
        else:
            from .models import Experiment
            experiment = Experiment.objects.get(identifier=experiment_identifier)

        # Get the user's profile for this experiment
        user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
        if not user_profile:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': 'User profile not found for this experiment'
                }, status=403)
            raise PermissionDenied("User profile not found for this experiment")

        # Check if user is banned
        if user_profile.is_banned:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': 'Your account has been suspended. You cannot perform this action at this time.'
                }, status=403)
            raise PermissionDenied("Your account has been suspended. You cannot perform this action at this time.")

        return view_func(request, *args, **kwargs)
    return _wrapped_view 