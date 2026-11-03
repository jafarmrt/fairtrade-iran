from wagtail.snippets.views.snippets import SnippetViewSet

from .models import Payment


class PaymentViewSet(SnippetViewSet):
    """Every online payment attempt, for the finance working group and reconciliation with the bank."""

    model = Payment
    icon = "password"
    menu_label = "پرداخت‌های آنلاین"
    inspect_view_enabled = True
    list_display = ["created_at", "purpose", "description", "amount", "status", "ref_id", "provider"]
    list_filter = ["status", "purpose", "provider"]
    list_export = ["created_at", "paid_at", "purpose", "description", "amount", "status", "ref_id", "card",
                   "provider", "mobile", "email", "error"]
    search_fields = ["description", "ref_id", "authority", "mobile", "email"]

# Registered in the admin menu by shop/wagtail_hooks.py, in the «فروشگاه» group.
