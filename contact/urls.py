from django.urls import path

from . import views

urlpatterns = [
    path("complaint-files/<int:pk>/", views.complaint_file, name="complaint_file"),
]
