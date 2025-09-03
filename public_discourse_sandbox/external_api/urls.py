from django.urls import path

from .views import get_posts
from .views import list_routes
from .views import post_detail

app_name = "external_api"

urlpatterns = [
    path("", list_routes),
    path("posts/", get_posts),
    path("posts/<uuid:pk>", post_detail),
    # path("auth/", include("rest_framework.urls", namespace="rest_framework")),  # noqa: E501, ERA001
]
