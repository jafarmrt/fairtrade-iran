from django.db import transaction
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel, ObjectList, TabbedInterface
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.admin.views.generic import EditView

from . import notifications
from .models import WholesaleInquiry


class InquiryEditView(EditView):
    def save_instance(self):
        instance = super().save_instance()
        # Producers the House added by hand hear about the enquiry once it is saved.
        transaction.on_commit(lambda: notifications.notify_new_shares(instance))
        return instance


class InquiryViewSet(ModelViewSet):
    """
    Wholesale enquiries. seed_content gives the permissions to the secretariat
    and the market development working group. Buyers send them from the
    website, so the 'add' view is only for enquiries that arrive by e-mail or phone.
    """

    model = WholesaleInquiry
    icon = "list-ul"
    menu_label = "سفارش‌های عمده"
    add_to_admin_menu = False  # it is in the «فروشگاه» menu group (shop/wagtail_hooks.py)
    copy_view_enabled = False
    edit_view_class = InquiryEditView
    list_display = ["tracking_code", "company", "country", "buyer_type", "line_count", "status", "created_at"]
    list_filter = ["status", "buyer_type", "language"]
    search_fields = ["tracking_code", "company", "contact_name", "email", "country", "message"]
    list_export = ["tracking_code", "created_at", "company", "contact_name", "email", "phone", "country", "city",
                   "website", "buyer_type", "incoterm", "destination", "needed_by", "other_products", "message",
                   "status"]
    export_filename = "wholesale-enquiries"
    edit_handler = TabbedInterface([
        ObjectList([
            MultiFieldPanel([
                FieldRowPanel([FieldPanel("company"), FieldPanel("buyer_type")]),
                FieldRowPanel([FieldPanel("contact_name"), FieldPanel("email")]),
                FieldRowPanel([FieldPanel("phone"), FieldPanel("website")]),
                FieldRowPanel([FieldPanel("country"), FieldPanel("city")]),
            ], heading="خریدار"),
            MultiFieldPanel([
                FieldRowPanel([FieldPanel("incoterm"), FieldPanel("destination")]),
                FieldPanel("needed_by"),
                FieldPanel("other_products"),
                FieldPanel("message"),
            ], heading="شرایط و توضیحات"),
            InlinePanel("lines", heading="محصولات درخواستی", label="قلم"),
        ], heading="درخواست"),
        ObjectList([
            InlinePanel(
                "producers", heading="تولیدکنندگان", label="تولیدکننده",
                help_text="هر تولیدکننده‌ای که این‌جا اضافه کنید، پس از ذخیره با ایمیل و پیامک خبردار می‌شود و "
                          "درخواست را در پنل اعضای خود می‌بیند. پاسخ تولیدکننده هم این‌جا دیده می‌شود.",
            ),
        ], heading="ارجاع و پاسخ تولیدکنندگان"),
        ObjectList([FieldPanel("status"), FieldPanel("house_notes")], heading="پیگیری خانه"),
    ])


# Registered, with its menu item, in the «فروشگاه» group by shop/wagtail_hooks.py.
inquiry_viewset = InquiryViewSet("wholesale_inquiries")
