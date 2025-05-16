from django.urls import path

from public_discourse_sandbox.users.views import (
    user_detail_view,
    user_redirect_view,
    user_update_view,
    user_profile_detail_view,
    update_profile_view,
    update_name_view,
    CustomEmailVerificationSentView,
    CustomSignupView,
)

app_name = "users"
urlpatterns = [
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("~update/", view=user_update_view, name="update"),
    path("<uuid:pk>/", view=user_detail_view, name="detail"),
    path("<str:experiment_identifier>/<uuid:pk>/", view=user_profile_detail_view, name="detail_with_experiment"),
    path("<str:experiment_identifier>/update-profile/", view=update_profile_view, name="update_profile"),
    path('email/verification-sent/', CustomEmailVerificationSentView.as_view(),
         name='account_email_verification_sent'),
    path('signup-with-profile/', CustomSignupView.as_view(), name='signup_with_profile'),
    path('update-name/', view=update_name_view, name='update_name'),
]
