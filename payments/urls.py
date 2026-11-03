from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("pay/<uuid:uid>/return/", views.callback, name="callback"),
    path("pay/<uuid:uid>/test-gateway/", views.test_gateway, name="test_gateway"),
]
