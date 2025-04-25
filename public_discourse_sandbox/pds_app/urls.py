from django.urls import path
from django.views.generic import TemplateView

# Import views using absolute import path for Celery compatibility
from public_discourse_sandbox.pds_app.views import HomeView, ExploreView
from public_discourse_sandbox.pds_app.api import (
    create_comment, get_post_replies,
    delete_post, ban_user, unban_user
)

urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/landing.html"), name="landing"),
    path("about/", TemplateView.as_view(template_name="pages/about.html"), name="about"),
    # URLs with experiment identifier
    path("<str:experiment_identifier>/home/", HomeView.as_view(), name="home_with_experiment"),
    path("<str:experiment_identifier>/explore/", ExploreView.as_view(), name="explore_with_experiment"),
    path("<str:experiment_identifier>/create-comment/", create_comment, name="create_comment_with_experiment"),
    path("<str:experiment_identifier>/get-replies/<uuid:post_id>/", get_post_replies, name="get_replies_with_experiment"),
    path("<str:experiment_identifier>/api/posts/<uuid:post_id>/delete/", delete_post, name="delete_post_with_experiment"),
    path("<str:experiment_identifier>/api/users/<uuid:user_profile_id>/ban/", ban_user, name="ban_user_with_experiment"),
    path("<str:experiment_identifier>/api/users/<uuid:user_profile_id>/unban/", unban_user, name="unban_user_with_experiment"),
    # URLs without experiment identifier (will use last_accessed)
    path("home/", HomeView.as_view(), name="home"),
    path("explore/", ExploreView.as_view(), name="explore"),
    path("create-comment/", create_comment, name="create_comment"),
    path("get-replies/<uuid:post_id>/", get_post_replies, name="get_replies"),
    path("api/posts/<uuid:post_id>/delete/", delete_post, name="delete_post"),
    path("api/users/<uuid:user_profile_id>/ban/", ban_user, name="ban_user"),
    path("api/users/<uuid:user_profile_id>/unban/", unban_user, name="unban_user"),
]
