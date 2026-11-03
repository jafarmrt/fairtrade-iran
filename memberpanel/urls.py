from django.urls import path

from . import views

app_name = "panel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("password/reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/set/<uidb64>/<token>/", views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password/set/done/", views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("password/change/", views.PasswordChangeView.as_view(), name="password_change"),
    path("<int:member_id>/profile/", views.profile, name="profile"),
    path("<int:member_id>/products/", views.product_list, name="products"),
    path("<int:member_id>/products/new/", views.product_add, name="product_add"),
    path("<int:member_id>/products/<int:product_id>/", views.product_edit, name="product_edit"),
    path("<int:member_id>/products/<int:product_id>/delete/", views.product_delete, name="product_delete"),
]
