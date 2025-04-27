from .models import DigitalTwin
from django.contrib.auth.models import User
from public_discourse_sandbox.pds_app.models import Experiment

def active_bots(request):
    """
    Context processor that adds active bots to all templates.
    This allows us to display the active bots count in the sidebar
    without having to add it to every view's context.
    """
    if not request.user.is_authenticated:
        return {'active_bots': []}
    
    # Get the current experiment from the URL or session
    experiment_identifier = request.resolver_match.kwargs.get('experiment_identifier')
    if not experiment_identifier:
        return {'active_bots': []}
    
    try:
        experiment = Experiment.objects.get(identifier=experiment_identifier)
        user_profile = request.user.userprofile_set.filter(experiment=experiment).first()
        if not user_profile:
            return {'active_bots': []}
        
        return {
            'active_bots': DigitalTwin.objects.filter(
                is_active=True, 
                user_profile__experiment=experiment
            )
        }
    except Experiment.DoesNotExist:
        return {'active_bots': []}

def user_experiments(request):
    """
    Context processor that adds the user's experiments to the template context.
    Returns an empty list if user is not authenticated.
    """
    if not request.user.is_authenticated:
        return {'user_experiments': [], 'current_experiment_identifier': None}
    
    # Get all experiments where the user has a UserProfile
    experiments = Experiment.objects.filter(
        userprofile__user=request.user
    ).distinct().order_by('name')
    
    # Get the current experiment identifier from the URL
    current_experiment_identifier = request.resolver_match.kwargs.get('experiment_identifier')
    
    return {
        'user_experiments': experiments,
        'current_experiment_identifier': current_experiment_identifier
    }
