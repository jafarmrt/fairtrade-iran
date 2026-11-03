from django.urls import path

from appeals import views as appeal_views
from assembly import panel_views as assembly_views
from shop import panel_views as shop_views
from standing import panel_views as standing_views
from wholesale import views as wholesale_views

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
    path("<int:member_id>/membership/", standing_views.membership, name="membership"),
    path("<int:member_id>/products/", views.product_list, name="products"),
    path("<int:member_id>/products/new/", views.product_add, name="product_add"),
    path("<int:member_id>/products/<int:product_id>/", views.product_edit, name="product_edit"),
    path("<int:member_id>/products/<int:product_id>/delete/", views.product_delete, name="product_delete"),
    path("<int:member_id>/orders/", shop_views.orders, name="orders"),
    path("<int:member_id>/orders/<int:order_id>/", shop_views.order_detail, name="order"),
    path("<int:member_id>/orders/<int:order_id>/invoice/", shop_views.order_invoice, name="order_invoice"),
    path("<int:member_id>/orders/<int:order_id>/receipt/", shop_views.order_receipt, name="order_receipt"),
    path("<int:member_id>/selling/", shop_views.selling, name="selling"),
    path("<int:member_id>/certificate/", views.certificate, name="certificate"),
    path("<int:member_id>/complaints/", appeal_views.complaints, name="complaints"),
    path("<int:member_id>/appeals/", appeal_views.appeals, name="appeals"),
    path("<int:member_id>/appeals/new/", appeal_views.appeal_new, name="appeal_new"),
    path("<int:member_id>/assembly/", assembly_views.assembly_list, name="assemblies"),
    path("<int:member_id>/assembly/<int:pk>/", assembly_views.assembly_detail, name="assembly"),
    path("<int:member_id>/assembly/<int:pk>/check-in/", assembly_views.assembly_check_in, name="assembly_check_in"),
    path("<int:member_id>/assembly/<int:pk>/vote/<int:item_id>/", assembly_views.assembly_vote,
         name="assembly_vote"),
    path("<int:member_id>/wholesale/", wholesale_views.inquiry_list, name="wholesale"),
    path("<int:member_id>/wholesale/<int:share_id>/", wholesale_views.inquiry_detail, name="wholesale_detail"),
]
