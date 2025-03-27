from django.urls import path
from django.views.generic import TemplateView

# Import views using absolute import path for Celery compatibility
from public_discourse_sandbox.pds_app.views import HomeView, ExploreView

urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/landing.html"), name="landing"),
    path("about/", TemplateView.as_view(template_name="pages/about.html"), name="about"),
    path("home/", HomeView.as_view(), name="home"),
    path("explore/", ExploreView.as_view(), name="explore"),
]
