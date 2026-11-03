import datetime
import io

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import translation
from wagtail.admin.forms.models import WagtailAdminModelForm
from wagtail.models import Page

from core import money
from core.models import SiteSettings
from core.widgets import JalaliDateInput, JalaliDateTimeInput
from home.management.commands import seed_data as data
from members.models import Member


class MoneyDisplayTests(SimpleTestCase):
    def test_modes(self):
        with translation.override("fa"):
            self.assertEqual(money.amount(12_450_000, mode="rial"), "۱۲٬۴۵۰٬۰۰۰ ریال")
            self.assertEqual(money.amount(12_450_000, mode="toman"), "۱٬۲۴۵٬۰۰۰ تومان")
            self.assertEqual(money.amount(12_450_000, mode="both"), "۱٬۲۴۵٬۰۰۰ تومان (۱۲٬۴۵۰٬۰۰۰ ریال)")
            self.assertEqual(money.amount(12_345, mode="toman"), "۱٬۲۳۴٫۵ تومان")
        self.assertEqual(money.amount(12_450_000, lang="en", mode="toman"), "1,245,000 tomans")
        self.assertEqual(money.amount(12_450_000, lang="en", mode="rial"), "12,450,000 rials")


class MoneySettingTests(TestCase):
    def test_setting_changes_pages_and_emails(self):
        from shop.notifications import amount_text

        settings = SiteSettings.load()
        self.assertEqual(settings.price_display, "toman")  # default
        self.assertEqual(amount_text(5_000_000, "fa"), "۵۰۰٬۰۰۰ تومان")
        settings.price_display = "rial"
        settings.save()
        self.assertEqual(amount_text(5_000_000, "fa"), "۵٬۰۰۰٬۰۰۰ ریال")


class JalaliWidgetTests(SimpleTestCase):
    def test_date(self):
        w = JalaliDateInput()
        self.assertEqual(w.format_value(datetime.date(2026, 11, 3)), "1405/08/12")
        self.assertEqual(w.value_from_datadict({"d": "۱۴۰۵/۰۸/۱۲"}, {}, "d"), "2026-11-03")
        self.assertEqual(w.value_from_datadict({"d": "2026-11-03"}, {}, "d"), "2026-11-03")
        self.assertEqual(w.value_from_datadict({"d": "1405/13/40"}, {}, "d"), "1405/13/40")  # left for the field to reject

    def test_datetime(self):
        w = JalaliDateTimeInput()
        self.assertEqual(w.value_from_datadict({"d": "۱۴۰۵/۰۸/۱۲ ۱۸:۳۰"}, {}, "d"), "2026-11-03 18:30")
        self.assertEqual(w.value_from_datadict({"d": "1405/08/12"}, {}, "d"), "2026-11-03 00:00")
        self.assertEqual(w.format_value(datetime.datetime(2026, 11, 3, 18, 30)), "1405/08/12 18:30")


class AdminDateFieldTests(TestCase):
    def test_wagtail_admin_forms_use_jalali(self):
        from wagtail.admin.panels import FieldPanel, ObjectList

        form_class = ObjectList([FieldPanel("joined_on")]).bind_to_model(Member).get_form_class()
        self.assertTrue(issubclass(form_class, WagtailAdminModelForm))
        self.assertIsInstance(form_class.base_fields["joined_on"].widget, JalaliDateInput)
        form = form_class({"joined_on": "۱۴۰۵/۰۸/۱۲"}, instance=Member(name="آزمون"))
        form.is_valid()
        self.assertNotIn("joined_on", form.errors)
        self.assertEqual(form.cleaned_data["joined_on"], datetime.date(2026, 11, 3))


@override_settings(WAGTAILADMIN_BASE_URL="http://testserver")
class EditorialWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=io.StringIO())
        call_command("seed_content", stdout=io.StringIO())  # idempotent

    def test_pr_writes_board_publishes(self):
        pr_user = User.objects.create_user("pr", "pr@example.org", "pw", is_staff=True)
        pr_user.groups.add(Group.objects.get(name=data.PR))
        board_user = User.objects.create_user("board", "board@example.org", "pw", is_staff=True)
        board_user.groups.add(Group.objects.get(name=data.BOARD))
        for lang in ("fa", "en"):
            home = Page.objects.get(depth=2, locale__language_code=lang)
            news = home.get_children().first()
            self.assertEqual(news.get_workflow().name, data.EDITORIAL_WORKFLOW)
            pr = news.permissions_for_user(pr_user)
            self.assertTrue(pr.can_edit())
            self.assertFalse(pr.can_publish())
            self.assertTrue(news.permissions_for_user(board_user).can_publish())
        task = news.get_workflow().tasks.get().specific
        self.assertEqual(list(task.groups.values_list("name", flat=True)), [data.BOARD])
