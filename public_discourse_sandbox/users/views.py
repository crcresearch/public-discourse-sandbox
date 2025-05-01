from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import QuerySet
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import UpdateView
from django.shortcuts import get_object_or_404

from public_discourse_sandbox.users.models import User
from public_discourse_sandbox.pds_app.mixins import ExperimentContextMixin
from public_discourse_sandbox.pds_app.models import UserProfile


class UserDetailView(LoginRequiredMixin, ExperimentContextMixin, DetailView):
    model = User
    slug_field = "id"
    slug_url_kwarg = "id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add the experiment identifier to the context for the template
        if self.experiment:
            context['experiment_identifier'] = self.experiment.identifier
        return context


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self) -> str:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user.get_absolute_url()

    def get_object(self, queryset: QuerySet | None=None) -> User:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self) -> str:
        return reverse("users:detail", kwargs={"pk": self.request.user.pk})


user_redirect_view = UserRedirectView.as_view()


class UserProfileDetailView(LoginRequiredMixin, ExperimentContextMixin, DetailView):
    """
    View for displaying a user's profile within a specific experiment context.
    This view requires both a user ID and an experiment identifier in the URL.
    """
    model = UserProfile
    template_name = 'users/user_profile_detail.html'
    context_object_name = 'user_profile'
    
    def get_object(self, queryset=None):
        """
        Get the UserProfile object for the specified user and experiment.
        """
        user_id = self.kwargs.get('pk')
        user = get_object_or_404(User, id=user_id)
        return get_object_or_404(
            UserProfile,
            user=user,
            experiment=self.experiment
        )

user_profile_detail_view = UserProfileDetailView.as_view()
