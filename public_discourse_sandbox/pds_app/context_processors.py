from .models import DigitalTwin

def active_bots(request):
    """
    Context processor that adds active bots to all templates.
    This allows us to display the active bots count in the sidebar
    without having to add it to every view's context.
    """
    return {
        'active_bots': DigitalTwin.objects.filter(is_active=True)
    } 