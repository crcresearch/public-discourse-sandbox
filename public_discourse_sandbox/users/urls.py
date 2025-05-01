from django.urls import path

from public_discourse_sandbox.users.views import (
    user_detail_view,
    user_redirect_view,
    user_update_view,
    user_profile_detail_view,
)

app_name = "users"
urlpatterns = [
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("~update/", view=user_update_view, name="update"),
    path("<uuid:pk>/", view=user_detail_view, name="detail"),
    path("<str:experiment_identifier>/<uuid:pk>/", view=user_profile_detail_view, name="detail_with_experiment"),
]
