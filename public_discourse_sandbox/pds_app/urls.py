from django.urls import path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/landing.html"), name="landing"),
    path("about/", TemplateView.as_view(template_name="pages/about.html"), name="about"),
    path("home/", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    path("explore/", TemplateView.as_view(template_name="pages/explore.html"), name="explore"),
]
