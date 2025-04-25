from .models import DigitalTwin
from django.contrib.auth.models import User
from public_discourse_sandbox.pds_app.models import Experiment

def active_bots(request):
    """
    Context processor that adds active bots to all templates.
    This allows us to display the active bots count in the sidebar
    without having to add it to every view's context.
    """
    # If the user is authenticated and there is a user profile, get the active bots for the user's experiment
    if request.user.is_authenticated and hasattr(request.user, 'userprofile'):
        return {
            'active_bots': DigitalTwin.objects.filter(is_active=True, user_profile__experiment=request.user.userprofile.experiment)
        } 
    # If the user is not authenticated, return an empty list
    else:
        return {
            'active_bots': []
        }

def user_experiments(request):
    """
    Context processor that adds the user's experiments to the template context.
    Returns an empty list if user is not authenticated.
    """
    if not request.user.is_authenticated:
        return {'user_experiments': []}
    
    # Get all experiments where the user has a UserProfile
    experiments = Experiment.objects.filter(
        userprofile__user=request.user
    ).distinct().order_by('name')
    
    return {'user_experiments': experiments}
