from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from .models import Experiment, UserProfile

class ExperimentContextMixin:
    """
    Mixin to handle experiment context in views.
    Adds experiment context to the view and verifies user access.
    """
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.experiment = None
        if 'experiment_identifier' in kwargs:
            self.experiment = get_object_or_404(Experiment, identifier=kwargs['experiment_identifier'])
            
            # Verify user has access to this experiment
            if request.user.is_authenticated:
                try:
                    user_profile = request.user.userprofile
                    if user_profile.experiment != self.experiment:
                        raise PermissionDenied("You do not have access to this experiment")
                except UserProfile.DoesNotExist:
                    raise PermissionDenied("You do not have a profile in this experiment")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.experiment:
            context['experiment'] = self.experiment
        return context 