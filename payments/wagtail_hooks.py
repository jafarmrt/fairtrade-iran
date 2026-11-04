from django.utils.functional import cached_property
from wagtail.permission_policies import ModelPermissionPolicy
from wagtail.snippets.views.snippets import SnippetViewSet

from core.admin_columns import MoneyColumn

from .models import Payment

WRITE_ACTIONS = {"add", "change", "delete"}


class ReadOnlyPermissionPolicy(ModelPermissionPolicy):
    """
    Payments are written only by the gateway's answer. In the admin they can be listed,
    opened and exported, never added, edited or deleted, even by a superuser: a hand-made
    payment row would show a «افزودن» form with Django internals (content type, object id)
    and break reconciliation with the bank.
    """

    def user_has_permission(self, user, action):
        return action not in WRITE_ACTIONS and super().user_has_permission(user, action)

    def user_has_any_permission(self, user, actions):
        return super().user_has_any_permission(user, [a for a in actions if a not in WRITE_ACTIONS])

    def user_has_permission_for_instance(self, user, action, instance):
        return action not in WRITE_ACTIONS and super().user_has_permission_for_instance(user, action, instance)

    def user_has_any_permission_for_instance(self, user, actions, instance):
        actions = [a for a in actions if a not in WRITE_ACTIONS]
        return bool(actions) and super().user_has_any_permission_for_instance(user, actions, instance)


class PaymentViewSet(SnippetViewSet):
    """Every online payment attempt, for the finance working group and reconciliation with the bank."""

    model = Payment
    icon = "password"
    menu_label = "پرداخت‌های آنلاین"
    inspect_view_enabled = True
    list_display = ["created_at", "purpose", "description", MoneyColumn("amount", label="مبلغ"), "status", "ref_id", "provider"]
    list_filter = ["status", "purpose", "provider"]
    list_export = ["created_at", "paid_at", "purpose", "description", "amount", "status", "ref_id", "card",
                   "provider", "mobile", "email", "error"]
    search_fields = ["description", "ref_id", "authority", "mobile", "email"]

    @cached_property
    def permission_policy(self):
        return ReadOnlyPermissionPolicy(self.model)

# Registered in the admin menu by shop/wagtail_hooks.py, in the «فروشگاه» group.
