from django.urls import path

from public_discourse_sandbox.pds_app.api import ban_user
from public_discourse_sandbox.pds_app.api import create_comment
from public_discourse_sandbox.pds_app.api import delete_experiment
from public_discourse_sandbox.pds_app.api import delete_post
from public_discourse_sandbox.pds_app.api import get_post_replies
from public_discourse_sandbox.pds_app.api import handle_like
from public_discourse_sandbox.pds_app.api import repost
from public_discourse_sandbox.pds_app.api import unban_user
from public_discourse_sandbox.pds_app.api import update_last_accessed
from public_discourse_sandbox.pds_app.external_api import api_get_post_by_id
from public_discourse_sandbox.pds_app.external_api import api_home_timeline
from public_discourse_sandbox.pds_app.external_api import api_user_experiments
from public_discourse_sandbox.pds_app.views import AboutView
from public_discourse_sandbox.pds_app.views import AcceptInvitationView
from public_discourse_sandbox.pds_app.views import CreateExperimentView
from public_discourse_sandbox.pds_app.views import CreateProfileView
from public_discourse_sandbox.pds_app.views import EnrollDigitalTwinView
from public_discourse_sandbox.pds_app.views import ExperimentDetailView
from public_discourse_sandbox.pds_app.views import ExploreView
from public_discourse_sandbox.pds_app.views import FollowView

# Import views using absolute import path for Celery compatibility
from public_discourse_sandbox.pds_app.views import HomeView
from public_discourse_sandbox.pds_app.views import InviteUserView
from public_discourse_sandbox.pds_app.views import LandingView
from public_discourse_sandbox.pds_app.views import ModeratorDashboardView
from public_discourse_sandbox.pds_app.views import NotificationsView
from public_discourse_sandbox.pds_app.views import ResearcherToolsView
from public_discourse_sandbox.pds_app.views import SettingsView
from public_discourse_sandbox.pds_app.views import UserProfileDetailView
from public_discourse_sandbox.pds_app.views import create_new_token_view

urlpatterns = [
    path("", LandingView.as_view(), name="landing"),
    path("about/", AboutView.as_view(), name="about"),
    path("researcher-tools/", ResearcherToolsView.as_view(), name="researcher_tools"),
    path(
        "create-experiment/", CreateExperimentView.as_view(), name="create_experiment",
    ),
    path(
        "experiment/<str:experiment_identifier>/",
        ExperimentDetailView.as_view(),
        name="experiment_detail",
    ),
    path(
        "experiment/<str:experiment_identifier>/delete/",
        delete_experiment,
        name="delete_experiment",
    ),
    path(
        "accept-invitation/<str:experiment_identifier>/<str:email>/",
        AcceptInvitationView.as_view(),
        name="accept_invitation",
    ),
    path("settings/", SettingsView.as_view(), name="settings"),
    # URLs with experiment identifier
    path(
        "<str:experiment_identifier>/about/",
        AboutView.as_view(),
        name="about_with_experiment",
    ),
    path(
        "<str:experiment_identifier>/home/",
        HomeView.as_view(),
        name="home_with_experiment",
    ),
    path(
        "<str:experiment_identifier>/explore/",
        ExploreView.as_view(),
        name="explore_with_experiment",
    ),
    path(
        "<str:experiment_identifier>/notifications/",
        NotificationsView.as_view(),
        name="notifications_with_experiment",
    ),
    path(
        "<str:experiment_identifier>/moderator/",
        ModeratorDashboardView.as_view(),
        name="moderator_dashboard",
    ),
    path(
        "<str:experiment_identifier>/create-comment/",
        create_comment,
        name="create_comment_with_experiment",
    ),
    path(
        "<str:experiment_identifier>/get-replies/<uuid:post_id>/",
        get_post_replies,
        name="get_replies_with_experiment",
    ),
    path(
        "<str:experiment_identifier>/api/posts/<uuid:post_id>/delete/",
        delete_post,
        name="delete_post_with_experiment",
    ),
    path(
        "<str:experiment_identifier>/api/posts/<uuid:post_id>/like/",
        handle_like,
        name="like_post_with_experiment",
    ),
    path(
        "<str:experiment_identifier>/invite/",
        InviteUserView.as_view(),
        name="invite_user",
    ),
    path(
        "<str:experiment_identifier>/enroll-digital-twin/",
        EnrollDigitalTwinView.as_view(),
        name="enroll_digital_twin",
    ),
    path(
        "<str:experiment_identifier>/create-profile/",
        CreateProfileView.as_view(),
        name="create_profile",
    ),
    path(
        "<str:experiment_identifier>/profile/<uuid:pk>/",
        UserProfileDetailView.as_view(),
        name="user_profile_detail",
    ),
    # API endpoints
    path(
        "api/users/<uuid:user_profile_id>/ban/",
        ban_user,
        name="ban_user_with_experiment",
    ),
    path(
        "api/users/<uuid:user_profile_id>/unban/",
        unban_user,
        name="unban_user_with_experiment",
    ),
    path(
        "api/update-last-accessed/", update_last_accessed, name="update_last_accessed",
    ),
    path(
        "api/users/<uuid:user_profile_id>/follow/",
        FollowView.as_view(),
        name="follow_user",
    ),
    path(
        "<str:experiment_identifier>/api/users/<uuid:user_profile_id>/follow/",
        FollowView.as_view(),
        name="follow_user_with_experiment",
    ),
    path("create_new_api_token/", create_new_token_view, name="create_new_api_token"),
    # URLs without experiment identifier (will use last_accessed)
    path("home/", HomeView.as_view(), name="home"),
    path("explore/", ExploreView.as_view(), name="explore"),
    path("notifications/", NotificationsView.as_view(), name="notifications"),
    path("get-replies/<uuid:post_id>/", get_post_replies, name="get_replies"),
    path("api/posts/<uuid:post_id>/delete/", delete_post, name="delete_post"),
    path("api/posts/<uuid:post_id>/like/", handle_like, name="like_post"),
    path("api/users/<uuid:user_profile_id>/ban/", ban_user, name="ban_user"),
    path("api/users/<uuid:user_profile_id>/unban/", unban_user, name="unban_user"),
    path("post/<uuid:post_id>/like/", handle_like, name="like_post"),
    path("post/<uuid:post_id>/repost/", repost, name="repost_post"),

    # External API Endposts
    path("api/v1/<str:experiment_id>/posts/home-timeline/", api_home_timeline, name="api_home_timeline"),
    path("api/v1/<str:experiment_id>/posts/<uuid:pk>", api_get_post_by_id),
    path("api/v1/user/discourses/", api_user_experiments, name="api_user_experiments"),
]
