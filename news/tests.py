import datetime

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone, translation
from wagtail.models import Locale

from core.jalali import format_jalali, gregorian_to_jalali
from news.models import NewsIndexPage, NewsPage


class JalaliTests(TestCase):
    def test_known_dates(self):
        self.assertEqual(gregorian_to_jalali(2026, 11, 2), (1405, 8, 11))
        self.assertEqual(gregorian_to_jalali(2025, 3, 21), (1404, 1, 1))
        self.assertEqual(gregorian_to_jalali(2026, 3, 20), (1404, 12, 29))

    def test_format_uses_persian_digits_and_month(self):
        self.assertEqual(format_jalali(datetime.date(2026, 11, 2)), "۱۱ آبان ۱۴۰۵")


class NewsPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=open("/dev/null", "w"))
        fa = Locale.objects.get(language_code="fa")
        cls.index = NewsIndexPage.objects.get(locale=fa)
        cls.event = NewsPage(
            title="نمایشگاه صنایع دستی", slug="fair", kind="event", date=datetime.date(2026, 11, 2),
            event_start=timezone.now() + datetime.timedelta(days=5), event_location="تهران",
        )
        cls.index.add_child(instance=cls.event)
        cls.event.save_revision().publish()

    def test_index_and_item_render_in_both_languages(self):
        for url in ["/fa/news/", "/en/news/", "/fa/news/website-launch/", "/en/news/website-launch/", "/fa/news/fair/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_persian_dates_are_jalali(self):
        response = self.client.get("/fa/news/fair/")
        self.assertContains(response, "۱۱ آبان ۱۴۰۵")
        self.assertContains(response, "تهران")

    def test_filter_by_kind(self):
        response = self.client.get("/fa/news/?kind=event")
        self.assertContains(response, "نمایشگاه صنایع دستی")
        self.assertNotContains(response, "وب‌سایت خانه تجارت عادلانه ایران راه‌اندازی شد")

    def test_upcoming_events_box(self):
        self.assertContains(self.client.get("/fa/news/"), "رویدادهای پیش رو")

    def test_latest_news_on_home_page(self):
        self.assertContains(self.client.get("/fa/"), "تازه‌ترین خبرها")
        self.assertContains(self.client.get("/en/"), "The Fair Trade House of Iran website is live")

    def test_event_needs_start_time(self):
        page = NewsPage(title="x", slug="x", kind="event")
        with self.assertRaises(ValidationError):
            with translation.override("fa"):
                page.full_clean()
