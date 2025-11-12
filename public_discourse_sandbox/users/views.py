from allauth.account.views import EmailVerificationSentView
from allauth.account.views import SignupView
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import QuerySet
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import UpdateView

from public_discourse_sandbox.pds_app.decorators import check_banned
from public_discourse_sandbox.pds_app.mixins import ExperimentContextMixin
from public_discourse_sandbox.pds_app.models import Experiment
from public_discourse_sandbox.pds_app.models import ExperimentInvitation
from public_discourse_sandbox.pds_app.models import Post
from public_discourse_sandbox.pds_app.models import SocialNetwork
from public_discourse_sandbox.pds_app.models import UserProfile
from public_discourse_sandbox.users.models import User

from .forms import CustomSignupForm

User = get_user_model()


class UserDetailView(LoginRequiredMixin, ExperimentContextMixin, DetailView):
    model = User
    slug_field = "id"
    slug_url_kwarg = "id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add the experiment identifier to the context for the template
        if self.experiment:
            context["experiment_identifier"] = self.experiment.identifier
        return context


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self) -> str:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user.get_absolute_url()

    def get_object(self, queryset: QuerySet | None = None) -> User:
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
    template_name = "users/user_profile_detail.html"
    context_object_name = "viewed_profile"

    def get_object(self, queryset=None):
        """
        Get the UserProfile object for the specified user and experiment.
        """
        user_id = self.kwargs.get("pk")
        user = get_object_or_404(User, id=user_id)
        return get_object_or_404(
            UserProfile,
            user=user,
            experiment=self.experiment,
        )

    def get_context_data(self, **kwargs):
        """
        Add experiment and profile context to template context.
        """
        context = super().get_context_data(**kwargs)
        # The ExperimentContextMixin already adds:
        # - experiment
        # - current_user_profile (the current user's profile in this experiment)
        # - is_moderator (current user's moderator status)

        # Add the viewed profile's role information
        context["viewed_profile"] = self.object
        context["is_creator"] = self.object.user == self.experiment.creator

        # Add follower and following counts
        context["follower_count"] = SocialNetwork.objects.filter(
            target_node=self.object
        ).count()
        context["following_count"] = SocialNetwork.objects.filter(
            source_node=self.object
        ).count()

        # Get pagination parameters
        previous_post_id = self.request.GET.get("previous_post_id", None)
        page_size = self.request.GET.get(
            "page_size", 10
        )  # Default to 10 posts per page

        # Get all posts by this user (not deleted, ordered by newest first)
        # Add select_related and prefetch_related for efficient queries
        all_posts = (
            Post.all_objects.filter(user_profile=self.object, is_deleted=False)
            .select_related(
                "user_profile",
                "user_profile__user",
                "parent_post",
                "parent_post__user_profile",
                "parent_post__user_profile__user",
            )
            .prefetch_related("vote_set")
        )

        # Separate original posts and replies
        original_posts = all_posts.filter(parent_post__isnull=True)
        replies = all_posts.filter(parent_post__isnull=False)

        # If previous_post_id provided, paginate from that post
        if previous_post_id:
            try:
                previous_post = Post.objects.get(id=previous_post_id)
                original_posts = original_posts.filter(
                    created_date__lt=previous_post.created_date
                )
                replies = replies.filter(created_date__lt=previous_post.created_date)
            except Post.DoesNotExist:
                pass

        # Order by newest first and limit to page size
        context["user_original_posts"] = original_posts.order_by("-created_date")[
            : int(page_size)
        ]
        context["user_replies"] = replies.order_by("-created_date")[: int(page_size)]

        # Add counts for the tabs
        context["original_posts_count"] = original_posts.count()
        context["replies_count"] = replies.count()

        # Keep the original user_posts for backward compatibility (all posts)
        context["user_posts"] = all_posts.order_by("-created_date")[: int(page_size)]

        # Annotate each post with comment_count and has_user_voted for template compatibility
        current_user = self.request.user
        for post_list in [
            context["user_original_posts"],
            context["user_replies"],
            context["user_posts"],
        ]:
            for post in post_list:
                post.comment_count = post.get_comment_count()
                post.has_user_voted = post.vote_set.filter(
                    user_profile__user=current_user
                ).exists()

        # If HTMX request, map user_posts to posts for template compatibility
        if self.request.headers.get("HX-Request"):
            context["posts"] = context["user_posts"]

        # Add whether the current user is following the viewed profile
        current_user_profile = context.get("current_user_profile")
        if current_user_profile:
            context["is_following_viewed_profile"] = SocialNetwork.objects.filter(
                source_node=current_user_profile, target_node=self.object
            ).exists()
        else:
            context["is_following_viewed_profile"] = False

        # Followers: UserProfiles that follow this profile
        follower_links = SocialNetwork.objects.filter(target_node=self.object)
        context["followers"] = UserProfile.objects.filter(
            id__in=follower_links.values_list("source_node", flat=True)
        )

        # Following: UserProfiles that this profile follows
        following_links = SocialNetwork.objects.filter(source_node=self.object)
        context["following"] = UserProfile.objects.filter(
            id__in=following_links.values_list("target_node", flat=True)
        )

        return context

    @method_decorator(check_banned)
    def get(self, request, *args, **kwargs):
        """Override get to handle HTMX requests."""
        if request.headers.get("HX-Request"):
            self.template_name = "partials/_post_list.html"
        return super().get(request, *args, **kwargs)


user_profile_detail_view = UserProfileDetailView.as_view()


@method_decorator(require_POST, name="dispatch")
class UpdateProfileView(LoginRequiredMixin, ExperimentContextMixin, View):
    """
    View for handling profile updates via AJAX.
    """

    def post(self, request, *args, **kwargs):
        try:
            user_profile = request.user.userprofile_set.get(experiment=self.experiment)

            # Update profile fields
            if "display_name" in request.POST:
                user_profile.display_name = request.POST["display_name"]
            if "username" in request.POST:
                # Check if username is already taken in this experiment
                if (
                    UserProfile.objects.filter(
                        experiment=self.experiment,
                        username=request.POST["username"],
                    )
                    .exclude(id=user_profile.id)
                    .exists()
                ):
                    return JsonResponse(
                        {
                            "success": False,
                            "error": "This username is already taken in this experiment",
                        },
                        status=400,
                    )
                user_profile.username = request.POST["username"]
            if "bio" in request.POST:
                user_profile.bio = request.POST["bio"]

            # Handle profile picture
            if "profile_picture" in request.FILES:
                user_profile.profile_picture = request.FILES["profile_picture"]

            # Handle banner picture
            if "banner_picture" in request.FILES:
                user_profile.banner_picture = request.FILES["banner_picture"]

            user_profile.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Profile updated successfully",
                }
            )

        except Exception as e:
            return JsonResponse(
                {
                    "success": False,
                    "error": str(e),
                },
                status=400,
            )


update_profile_view = UpdateProfileView.as_view()


class CustomSignupView(SignupView):
    """
    Custom signup view that uses our form with profile fields.
    If accessed without experiment parameter, redirects to original signup.
    Email parameter is optional for initial signup from landing page.
    """

    form_class = CustomSignupForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Get experiment and email from URL parameters or POST data
        experiment_identifier = self.request.GET.get(
            "experiment"
        ) or self.request.POST.get("experiment")
        email = self.request.GET.get("email") or self.request.POST.get("email")

        if experiment_identifier:
            try:
                experiment = Experiment.objects.get(identifier=experiment_identifier)
                kwargs["experiment"] = experiment

                # If email is provided, check for invitation
                if email:
                    try:
                        invitation = ExperimentInvitation.objects.get(
                            experiment=experiment,
                            email=email,
                            is_accepted=False,
                            is_deleted=False,
                        )
                        kwargs["initial"] = {"email": email}
                    except ExperimentInvitation.DoesNotExist:
                        pass
            except Experiment.DoesNotExist:
                pass
        return kwargs

    def get(self, request, *args, **kwargs):
        # Only redirect if no experiment is provided
        if not request.GET.get("experiment"):
            return redirect("account_signup")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add experiment and email to form context for hidden fields
        context["experiment"] = self.request.GET.get("experiment")
        context["email"] = self.request.GET.get("email")
        return context

    def get_success_url(self):
        # After successful signup, redirect to email verification
        return reverse("account_email_verification_sent")

    def form_valid(self, form):
        # Call parent method to save the User
        response = super().form_valid(form)

        user = self.user
        experiment = form.experiment
        if user and experiment:
            # Check if the user already has a profile for this experiment
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                experiment=experiment,
                defaults={
                    "username": form.cleaned_data.get("user_name"),
                    "display_name": form.cleaned_data.get("display_name"),
                    "bio": form.cleaned_data.get("bio"),
                    "phone_number": form.cleaned_data.get("phone_number"),
                    "dorm_name": form.cleaned_data.get("dorm_name"),
                },
            )

            # Upload profile/banner pictures if provided
            if created:
                if form.cleaned_data.get("profile_picture"):
                    profile.profile_picture = form.cleaned_data.get("profile_picture")
                if form.cleaned_data.get("banner_picture"):
                    profile.banner_picture = form.cleaned_data.get("banner_picture")
                profile.save()

            # If there was an invitation, mark it as accepted
            email = form.cleaned_data.get("email")
            if email:
                try:
                    invitation = ExperimentInvitation.objects.get(
                        experiment=experiment,
                        email=email,
                        is_accepted=False,
                        is_deleted=False,
                    )
                    invitation.is_accepted = True
                    invitation.save()
                except ExperimentInvitation.DoesNotExist:
                    # No invitation found, which is fine for direct signups
                    pass

        return response


class CustomEmailVerificationSentView(EmailVerificationSentView):
    """
    Custom view to handle email verification and redirect to create profile
    if there's a pending invitation.
    """

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)

        # Check if there's a pending invitation
        pending_invitation = request.session.get("pending_invitation")
        if pending_invitation:
            # Clear the session data
            del request.session["pending_invitation"]

            # Redirect to create profile
            return redirect(
                "create_profile",
                experiment_identifier=pending_invitation["experiment_identifier"],
            )

        return response


@login_required
def update_name_view(request):
    """
    Simple view to update a user's name field.
    """
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if name:
            user = request.user
            user.name = name
            user.save(update_fields=["name"])
            messages.success(request, _("Name successfully updated"))
        else:
            messages.error(request, _("Name cannot be empty"))

    # Redirect back to settings page
    return HttpResponseRedirect(reverse("settings"))
