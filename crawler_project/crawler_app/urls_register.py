from django.urls import path
from .views_register import register

urlpatterns = [
    path("", register, name="register"),
]
