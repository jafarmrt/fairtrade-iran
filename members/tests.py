from django.core.management import call_command
from django.test import TestCase

from members.models import DirectorySettings, Member, Region
from products.models import Category, Product, ShopSettings


def seed():
    call_command("seed_content", stdout=open("/dev/null", "w"))


class SeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()

    def test_founding_producers_seeded(self):
        producers = Member.objects.filter(is_founding=True, member_type=Member.PRODUCER)
        self.assertEqual(producers.count(), 7)
        self.assertTrue(all(m.name_en for m in producers))
        self.assertEqual(Member.objects.get(slug="armoz").region.name, "هرمزگان")

    def test_seed_is_idempotent_and_keeps_edits(self):
        Member.objects.filter(slug="armoz").update(summary="ویرایش ادمین")
        seed()
        self.assertEqual(Member.objects.filter(is_founding=True).count(), 9)
        self.assertEqual(Member.objects.get(slug="armoz").summary, "ویرایش ادمین")
        self.assertEqual(Region.objects.count(), 31)

    def test_editor_groups_can_manage_directory(self):
        from django.contrib.auth.models import Group

        perms = set(Group.objects.get(name="روابط عمومی").permissions.values_list("codename", flat=True))
        self.assertTrue({"change_member", "add_product", "change_shopsettings"} <= perms)


class DirectoryPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()
        cls.armoz = Member.objects.get(slug="armoz")
        cls.armoz.instagram_url = "https://instagram.com/armoz"
        cls.armoz.save()
        Member.objects.create(name="عضو بی‌نام انگلیسی", slug="fa-only", status=Member.TRIAL)
        Member.objects.create(name="عضو معلق", name_en="Suspended one", slug="suspended", status=Member.SUSPENDED)
        cat = Category.objects.get(slug="food")
        cls.dates = Product.objects.create(member=cls.armoz, category=cat, name="خرما", name_en="Dates",
                                           slug="dates", price=1500000, is_featured=True)
        Product.objects.create(member=cls.armoz, name="محصول فارسی", slug="fa-product")

    def test_pages_render(self):
        for url in ["/fa/members/", "/en/members/", "/fa/members/armoz/", "/en/members/armoz/",
                    "/fa/shop/", "/en/shop/", "/fa/shop/dates/", "/en/shop/dates/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_english_hides_untranslated_items(self):
        self.assertContains(self.client.get("/fa/members/"), "عضو بی‌نام انگلیسی")
        self.assertNotContains(self.client.get("/en/members/"), "fa-only")
        self.assertEqual(self.client.get("/en/members/fa-only/").status_code, 404)
        self.assertContains(self.client.get("/fa/shop/"), "محصول فارسی")
        self.assertNotContains(self.client.get("/en/shop/"), "fa-product")

    def test_suspended_member_hidden(self):
        self.assertNotContains(self.client.get("/en/members/"), "Suspended one")
        self.assertEqual(self.client.get("/fa/members/suspended/").status_code, 404)

    def test_member_filters(self):
        response = self.client.get("/fa/members/?type=institution")
        self.assertContains(response, "هفت دست")
        self.assertNotContains(response, "پروندبوم")
        response = self.client.get(f"/fa/members/?region={self.armoz.region_id}")
        self.assertContains(response, "ارموز")
        self.assertNotContains(response, "پاپیتال")
        self.assertNotContains(self.client.get("/fa/members/?status=founding"), "عضو بی‌نام انگلیسی")
        self.assertContains(self.client.get("/fa/members/?q=Papital"), "پاپیتال")

    def test_product_filters(self):
        self.assertContains(self.client.get("/fa/shop/?category=food"), "خرما")
        self.assertNotContains(self.client.get("/fa/shop/?category=food"), "محصول فارسی")
        self.assertNotContains(self.client.get("/fa/shop/?member=papital"), "خرما")

    def test_direct_purchase_falls_back_to_member_link(self):
        response = self.client.get("/fa/shop/dates/")
        self.assertContains(response, 'href="https://instagram.com/armoz"')
        self.assertContains(response, ShopSettings.load().direct_purchase_label)
        self.dates.purchase_url = "https://shop.example/dates"
        self.dates.save()
        self.assertContains(self.client.get("/fa/shop/dates/"), 'href="https://shop.example/dates"')

    def test_button_label_editable(self):
        shop = ShopSettings.load()
        shop.direct_purchase_label_en = "Order now"
        shop.save()
        self.assertContains(self.client.get("/en/shop/dates/"), "Order now")

    def test_prices_hidden_in_english_by_default(self):
        self.assertContains(self.client.get("/fa/shop/dates/"), "۱٬۵۰۰٬۰۰۰")
        self.assertNotContains(self.client.get("/en/shop/dates/"), "1,500,000")

    def test_language_switch_on_detail_page(self):
        self.assertContains(self.client.get("/fa/members/armoz/"), 'href="/en/members/armoz/"')
        self.assertContains(self.client.get("/en/shop/dates/"), 'href="/fa/shop/dates/"')

    def test_home_shows_featured_sections(self):
        response = self.client.get("/fa/")
        self.assertContains(response, "خرما")
        self.assertContains(response, DirectorySettings.load().home_title)
        conf = DirectorySettings.load()
        conf.show_on_home = False
        conf.save()
        self.assertNotContains(self.client.get("/fa/"), conf.home_title)

    def test_auto_slug(self):
        member = Member.objects.create(name="گروه تازه", name_en="New Group")
        self.assertEqual(member.slug, "new-group")
        other = Member.objects.create(name="گروه تازه ۲", name_en="New Group")
        self.assertEqual(other.slug, "new-group-2")
