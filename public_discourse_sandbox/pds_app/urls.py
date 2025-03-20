from django.contrib import admin
from django.urls import include
from django.urls import path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include("users.urls")),
    path("", views.landing, name="landing"),
]
