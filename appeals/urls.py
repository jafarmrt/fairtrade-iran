from django.urls import path

from . import views

urlpatterns = [
    path("appeal-files/<int:pk>/", views.attachment, name="appeal_file"),
]
