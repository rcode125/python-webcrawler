from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("crawl/", views.start_crawl, name="start_crawl"),
    path("request-delete/", views.request_delete_view, name="request_delete"),
]
