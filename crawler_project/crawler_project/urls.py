from django.contrib import admin
from django.urls import path, include
from crawler_app import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # built-in auth views (login/logout/password reset)
    path("accounts/", include("django.contrib.auth.urls")),

    # registration
    path("accounts/register/", include("crawler_app.urls_register")),

    # logout
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # app views
    path("dashboard/", views.dashboard, name="dashboard"),
    path("crawl/", views.start_crawl, name="start_crawl"),

    # root URL → dashboard
    path("", views.dashboard, name="home"),

    path("crawler/", include("crawler_app.urls")),

]
