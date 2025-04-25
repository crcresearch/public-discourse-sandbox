from .models import DigitalTwin

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
