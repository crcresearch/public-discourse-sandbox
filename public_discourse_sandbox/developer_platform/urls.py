from django.urls import path

from . import views

app_name = "developer_platform"

urlpatterns = [path("", views.IndexView.as_view(), name="index")]
