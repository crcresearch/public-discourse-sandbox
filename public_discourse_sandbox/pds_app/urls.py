from django.urls import path
from django.views.generic import TemplateView

# Import views using absolute import path for Celery compatibility
from public_discourse_sandbox.pds_app.views import (
    HomeView, ExploreView, AboutView, LandingView, 
    ModeratorDashboardView, FollowView, ResearcherToolsView,
    ExperimentDetailView, CreateExperimentView, InviteUserView, EnrollDigitalTwinView,
    AcceptInvitationView, CreateProfileView, UserProfileDetailView, SettingsView
)
from public_discourse_sandbox.pds_app.api import (
    create_comment, get_post_replies,
    delete_post, ban_user, unban_user,
    update_last_accessed, handle_like, delete_experiment
)

urlpatterns = [
    path("", LandingView.as_view(), name="landing"),
    path("about/", AboutView.as_view(), name="about"),
    path("researcher-tools/", ResearcherToolsView.as_view(), name="researcher_tools"),
    path("create-experiment/", CreateExperimentView.as_view(), name="create_experiment"),
    path("experiment/<str:experiment_identifier>/", ExperimentDetailView.as_view(), name="experiment_detail"),
    path("experiment/<str:experiment_identifier>/delete/", delete_experiment, name="delete_experiment"),
    path("accept-invitation/<str:experiment_identifier>/<str:email>/", AcceptInvitationView.as_view(), name="accept_invitation"),
    path("settings/", SettingsView.as_view(), name="settings"),
    # URLs with experiment identifier
    path("<str:experiment_identifier>/about/", AboutView.as_view(), name="about_with_experiment"),
    path("<str:experiment_identifier>/home/", HomeView.as_view(), name="home_with_experiment"),
    path("<str:experiment_identifier>/explore/", ExploreView.as_view(), name="explore_with_experiment"),
    path("<str:experiment_identifier>/moderator/", ModeratorDashboardView.as_view(), name="moderator_dashboard"),
    path("<str:experiment_identifier>/create-comment/", create_comment, name="create_comment_with_experiment"),
    path("<str:experiment_identifier>/get-replies/<uuid:post_id>/", get_post_replies, name="get_replies_with_experiment"),
    path("<str:experiment_identifier>/api/posts/<uuid:post_id>/delete/", delete_post, name="delete_post_with_experiment"),
    path("<str:experiment_identifier>/api/posts/<uuid:post_id>/like/", handle_like, name="like_post_with_experiment"),
    path("<str:experiment_identifier>/invite/", InviteUserView.as_view(), name="invite_user"),
    path('<str:experiment_identifier>/enroll-digital-twin/', EnrollDigitalTwinView.as_view(), name='enroll_digital_twin'),
    path('<str:experiment_identifier>/create-profile/', CreateProfileView.as_view(), name='create_profile'),
    path("<str:experiment_identifier>/profile/<uuid:pk>/", UserProfileDetailView.as_view(), name="user_profile_detail"),
    # API endpoints
    path("api/users/<uuid:user_profile_id>/ban/", ban_user, name="ban_user_with_experiment"),
    path("api/users/<uuid:user_profile_id>/unban/", unban_user, name="unban_user_with_experiment"),
    path("api/update-last-accessed/", update_last_accessed, name="update_last_accessed"),
    path("api/users/<uuid:user_profile_id>/follow/", FollowView.as_view(), name="follow_user"),
    path("<str:experiment_identifier>/api/users/<uuid:user_profile_id>/follow/", FollowView.as_view(), name="follow_user_with_experiment"),
    # URLs without experiment identifier (will use last_accessed)
    path("home/", HomeView.as_view(), name="home"),
    path("explore/", ExploreView.as_view(), name="explore"),
    path("get-replies/<uuid:post_id>/", get_post_replies, name="get_replies"),
    path("api/posts/<uuid:post_id>/delete/", delete_post, name="delete_post"),
    path("api/posts/<uuid:post_id>/like/", handle_like, name="like_post"),
    path("api/users/<uuid:user_profile_id>/ban/", ban_user, name="ban_user"),
    path("api/users/<uuid:user_profile_id>/unban/", unban_user, name="unban_user"),
]
