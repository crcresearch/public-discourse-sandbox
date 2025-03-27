from django.urls import path
from django.views.generic import TemplateView

from .views.home import home
from .views.explore import explore

urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/landing.html"), name="landing"),
    path("about/", TemplateView.as_view(template_name="pages/about.html"), name="about"),
    path("home/", home, name="home"),
    path("explore/", explore, name="explore"),
]
