import io
import shutil
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from members.models import Member
from payments.models import Payment, PaymentSettings
from products.models import Product, ShopSettings
from sms import backends as sms_backends
from sms.models import SmsSettings

from . import services
from .models import Order, Purchase, Seller

QUIET = io.StringIO()
PRIVATE = tempfile.mkdtemp()

BUYER = {"buyer_name": "سارا احمدی", "phone": "09121234567", "email": "sara@example.org", "province": "تهران",
         "city": "تهران", "address": "خیابان آزادی، پلاک ۱", "postal_code": "1234567890", "note": "",
         "accept_terms": "on"}


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE, WAGTAILADMIN_BASE_URL="https://example.org",
                   SMS_BACKEND="sms.backends.LocmemBackend")
class ShopTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=QUIET)
        shop = ShopSettings.load()
        shop.commission_percent = 10
        shop.card_number = "6037-0000-0000-1111"
        shop.order_notification_email = "orders@example.org"
        shop.save()
        cls.house_member = Member.objects.get(slug="armoz")
        cls.direct_member = Member.objects.get(slug="papital")
        Seller.objects.create(member=cls.house_member, mode=Seller.Mode.HOUSE, shipping_fee=500_000,
                              free_shipping_over=10_000_000, sheba="IR000000000000000000000001")
        Seller.objects.create(member=cls.direct_member, mode=Seller.Mode.PRODUCER, card_number="6219-8600-0000-2222",
                              commission_percent=5)
        cls.mat = Product.objects.create(member=cls.house_member, name="حصیر", name_en="Mat", price=2_000_000,
                                         stock_quantity=3)
        cls.ring = Product.objects.create(member=cls.direct_member, name="انگشتر", name_en="Ring", price=4_000_000)
        cls.no_price = Product.objects.create(member=cls.house_member, name="سفارشی", price=None)
        cls.seller_user = User.objects.create_user("armoz", "armoz@example.org", "pw-12345")
        cls.house_member.managers.add(cls.seller_user)
        cls.direct_user = User.objects.create_user("papital", "papital@example.org", "pw-12345")
        cls.direct_member.managers.add(cls.direct_user)
        cls.staff = User.objects.create_user("finance", "finance@example.org", "pw-12345", is_staff=True)
        cls.staff.user_permissions.add(
            Permission.objects.get(codename="access_admin"), Permission.objects.get(codename="manage_orders"))
        sms = SmsSettings.load()
        sms.enabled = True
        sms.save()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(PRIVATE, ignore_errors=True)

    def setUp(self):
        sms_backends.outbox.clear()

    def add(self, product, quantity=1, lang="fa"):
        return self.client.post(f"/{lang}/shop/cart/", {"action": "add", "product": product.pk, "quantity": quantity})

    def checkout(self, lang="fa", **extra):
        return self.client.post(f"/{lang}/shop/checkout/", {**BUYER, **extra})


class CartTests(ShopTestCase):
    def test_product_page_shows_add_to_cart_only_when_sellable(self):
        response = self.client.get("/fa/shop/mat/")
        self.assertContains(response, "افزودن به سبد خرید")
        self.assertContains(response, 'name="product" value="%d"' % self.mat.pk)
        response = self.client.get(f"/fa/shop/{self.no_price.slug}/")
        self.assertNotContains(response, "افزودن به سبد خرید")

    def test_cart_is_off_in_english_by_default(self):
        response = self.client.get("/en/shop/mat/")
        self.assertNotContains(response, "Add to cart")
        self.add(self.mat, lang="en")
        self.assertEqual(self.client.session.get("shop_cart"), None)

    def test_member_without_seller_mode_keeps_direct_link(self):
        Seller.objects.filter(member=self.house_member).update(mode=Seller.Mode.NONE)
        self.assertFalse(Product.objects.get(pk=self.mat.pk).can_add_to_cart())

    def test_add_update_remove_and_header_link(self):
        self.add(self.mat, 2)
        self.add(self.ring)
        response = self.client.get("/fa/shop/cart/")
        self.assertContains(response, "حصیر")
        self.assertContains(response, "انگشتر")
        self.assertContains(response, 'class="cart-link"')
        self.assertEqual(response.context["cart_total"], 2 * 2_000_000 + 500_000 + 4_000_000)
        self.client.post("/fa/shop/cart/", {"action": "update", f"qty_{self.mat.pk}": "1", f"qty_{self.ring.pk}": "1"})
        self.assertEqual(self.client.session["shop_cart"], {str(self.mat.pk): 1, str(self.ring.pk): 1})
        self.client.post("/fa/shop/cart/", {"action": "remove", "product": self.ring.pk})
        self.assertEqual(self.client.session["shop_cart"], {str(self.mat.pk): 1})

    def test_quantity_is_capped_by_stock(self):
        self.add(self.mat, 9)
        response = self.client.get("/fa/shop/cart/")
        line = response.context["groups"][0].lines[0]
        self.assertEqual((line.quantity, line.reduced), (3, True))

    def test_reserved_slugs(self):
        product = Product.objects.create(member=self.house_member, name="Cart", name_en="cart", slug="cart")
        self.assertNotEqual(product.slug, "cart")


class CheckoutTests(ShopTestCase):
    def test_checkout_splits_orders_per_producer(self):
        self.add(self.mat, 2)
        self.add(self.ring)
        response = self.checkout()
        purchase = Purchase.objects.get()
        self.assertRedirects(response, f"/fa/shop/order/{purchase.code}/?new=1", fetch_redirect_response=False)
        house = purchase.orders.get(member=self.house_member)
        direct = purchase.orders.get(member=self.direct_member)
        self.assertEqual((house.payment_mode, house.subtotal, house.shipping, house.total, house.commission),
                         ("house", 4_000_000, 500_000, 4_500_000, 400_000))
        self.assertEqual((direct.payment_mode, direct.shipping, direct.total, direct.commission),
                         ("producer", 0, 4_000_000, 200_000))
        self.assertEqual(Product.objects.get(pk=self.mat.pk).stock_quantity, 1)
        self.assertEqual(self.client.session["shop_cart"], {})
        page = self.client.get(f"/fa/shop/order/{purchase.code}/")
        self.assertContains(page, purchase.code)
        self.assertContains(page, "6037 0000 0000 1111")  # House account for the House order
        self.assertContains(page, "6219 8600 0000 2222")  # producer's card for the direct order

    def test_notifications_on_checkout(self):
        self.add(self.mat)
        self.add(self.ring)
        with self.captureOnCommitCallbacks(execute=True):
            self.checkout()
        recipients = {tuple(m.to) for m in mail.outbox}
        self.assertIn(("sara@example.org",), recipients)
        self.assertIn(("armoz@example.org",), recipients)
        self.assertIn(("papital@example.org",), recipients)
        self.assertIn(("orders@example.org",), recipients)
        buyer_mail = next(m for m in mail.outbox if m.to == ["sara@example.org"])
        self.assertIn("حصیر", buyer_mail.body)
        self.assertIn("/fa/shop/order/", buyer_mail.body)
        self.assertTrue(any(s["to"] == ["09121234567"] for s in sms_backends.outbox))

    def test_last_item_cannot_be_sold_twice(self):
        Product.objects.filter(pk=self.mat.pk).update(stock_quantity=1)
        self.add(self.mat)
        Product.objects.filter(pk=self.mat.pk).update(stock_quantity=0, in_stock=False)
        response = self.checkout()
        self.assertEqual(Purchase.objects.count(), 0)
        self.assertRedirects(response, "/fa/shop/cart/", fetch_redirect_response=False)

    def test_stock_runs_out(self):
        self.add(self.mat, 3)
        self.checkout()
        product = Product.objects.get(pk=self.mat.pk)
        self.assertEqual((product.stock_quantity, product.in_stock), (0, False))

    def test_order_page_needs_code_and_phone(self):
        self.add(self.mat)
        self.checkout()
        purchase = Purchase.objects.get()
        other = self.client_class()
        response = other.get(f"/fa/shop/order/{purchase.code}/")
        self.assertRedirects(response, f"/fa/shop/orders/?code={purchase.code}", fetch_redirect_response=False)
        response = other.post("/fa/shop/orders/", {"code": purchase.code, "phone": "0912 000 0000"})
        self.assertContains(response, "پیدا نشد")
        response = other.post("/fa/shop/orders/", {"code": purchase.code.lower(), "phone": "+989121234567"})
        self.assertRedirects(response, f"/fa/shop/order/{purchase.code}/", fetch_redirect_response=False)

    def test_search_ignores_arabic_letters(self):
        Product.objects.create(member=self.house_member, name="کیک خرما", price=100_000)
        self.assertContains(self.client.get("/fa/shop/", {"q": "كيك"}), "کیک خرما")

    def test_short_stock_fixes_the_cart(self):
        self.add(self.mat, 3)
        Product.objects.filter(pk=self.mat.pk).update(stock_quantity=2)
        self.assertRedirects(self.checkout(), "/fa/shop/cart/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["shop_cart"], {str(self.mat.pk): 2})
        self.checkout()
        self.assertEqual(Purchase.objects.get().orders.get().items.get().quantity, 2)

    def test_iranian_fields_are_checked_and_normalised(self):
        self.add(self.mat)
        response = self.checkout(phone="0912", postal_code="123", province="")
        self.assertContains(response, "شماره موبایل باید ۱۱ رقم باشد")
        self.assertContains(response, "کد پستی باید ۱۰ رقم باشد")
        self.assertEqual(Purchase.objects.count(), 0)
        self.checkout(phone="۰۹۱۲ ۱۲۳ ۴۵۶۷", postal_code="۱۲۳۴۵-۶۷۸۹۰", buyer_name="سارا علي")
        purchase = Purchase.objects.get()
        self.assertEqual((purchase.phone, purchase.postal_code, purchase.buyer_name),
                         ("09121234567", "1234567890", "سارا علی"))
        other = self.client_class()
        response = other.post("/fa/shop/orders/", {"code": purchase.code, "phone": "۰۹۱۲۱۲۳۴۵۶۷"})
        self.assertRedirects(response, f"/fa/shop/order/{purchase.code}/", fetch_redirect_response=False)

    def test_rejected_receipt_restarts_payment_deadline(self):
        from django.utils import timezone

        from .services import cancel_overdue, log

        self.add(self.mat)
        self.checkout()
        order = Order.objects.get(member=self.house_member)
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timezone.timedelta(days=10))
        log(order, "reject_payment", "staff", None, "رسید خوانا نیست")
        self.assertEqual(cancel_overdue(), 0)
        order.events.update(created_at=timezone.now() - timezone.timedelta(days=10))
        self.assertEqual(cancel_overdue(), 1)

    def test_english_cart_when_enabled(self):
        shop = ShopSettings.load()
        shop.cart_enabled_en = True
        shop.save()
        self.add(self.mat, lang="en")
        response = self.checkout(lang="en")
        purchase = Purchase.objects.get()
        self.assertEqual(purchase.language, "en")
        page = self.client.get(f"/en/shop/order/{purchase.code}/")
        self.assertContains(page, "Pay the Fair Trade House")


class OrderFlowTests(ShopTestCase):
    def place(self, *products):
        for p in products:
            self.add(p)
        self.checkout()
        return Purchase.objects.latest("created_at")

    def test_house_order_receipt_confirm_ship_settle(self):
        purchase = self.place(self.mat)
        order = purchase.orders.get()
        receipt = SimpleUploadedFile("receipt.png", b"\x89PNG fake", content_type="image/png")
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/fa/shop/order/{purchase.code}/",
                             {"step": "payment_info", "order": order.pk, "reference": "123456", "receipt": receipt})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAYMENT_REVIEW)
        self.assertTrue(any("orders@example.org" in m.to for m in mail.outbox))

        # the seller cannot confirm a House payment
        self.client.force_login(self.seller_user)
        self.client.post(f"/fa/panel/{self.house_member.pk}/orders/{order.pk}/", {"action": "confirm"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAYMENT_REVIEW)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(f"/admin/shop_orders/{order.pk}/receipt/").status_code, 200)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/admin/shop_orders/{order.pk}/", {"action": "confirm"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual({m.to[0] for m in mail.outbox}, {"sara@example.org", "armoz@example.org"})

        self.client.force_login(self.seller_user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/fa/panel/{self.house_member.pk}/orders/{order.pk}/",
                             {"action": "ship", "tracking_code": "PST-998877"})
        order.refresh_from_db()
        self.assertEqual((order.status, order.tracking_code), (Order.Status.SHIPPED, "PST-998877"))
        self.assertTrue(order.needs_settlement)

        self.client.force_login(self.staff)
        self.client.post(f"/admin/shop_orders/{order.pk}/", {"action": "settle", "reference": "TR-1"})
        order.refresh_from_db()
        self.assertIsNotNone(order.settled_at)
        self.assertEqual(order.producer_share, order.total - order.commission)

    def test_direct_order_confirmed_by_producer(self):
        purchase = self.place(self.ring)
        order = purchase.orders.get()
        self.client.post(f"/fa/shop/order/{purchase.code}/", {"step": "payment_info", "order": order.pk,
                                                               "reference": "9988"})
        self.client.force_login(self.direct_user)
        response = self.client.get(f"/fa/panel/{self.direct_member.pk}/orders/")
        self.assertContains(response, order.code)
        self.client.post(f"/fa/panel/{self.direct_member.pk}/orders/{order.pk}/", {"action": "reject", "message": ""})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAYMENT_REVIEW)  # a reason is needed
        self.client.post(f"/fa/panel/{self.direct_member.pk}/orders/{order.pk}/", {"action": "confirm"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        # a producer cannot see another producer's orders
        self.assertEqual(self.client.get(f"/fa/panel/{self.house_member.pk}/orders/").status_code, 404)

    def test_cancel_returns_stock(self):
        purchase = self.place(self.mat)
        order = purchase.orders.get()
        self.assertEqual(Product.objects.get(pk=self.mat.pk).stock_quantity, 2)
        self.client.force_login(self.seller_user)
        self.client.post(f"/fa/panel/{self.house_member.pk}/orders/{order.pk}/", {"action": "cancel",
                                                                                   "message": "تمام شد"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(Product.objects.get(pk=self.mat.pk).stock_quantity, 3)

    def test_seller_cannot_cancel_paid_house_order(self):
        purchase = self.place(self.mat)
        order = purchase.orders.get()
        services.confirm_payment(order, self.staff)
        with self.assertRaises(services.OrderError):
            services.cancel(order, self.seller_user, "x", by=services.SELLER)

    def test_unpaid_orders_cancelled_by_daily_job(self):
        purchase = self.place(self.mat)
        Order.objects.filter(purchase=purchase).update(created_at=timezone.now() - timedelta(days=4))
        call_command("shop_daily", stdout=QUIET)
        self.assertEqual(purchase.orders.get().status, Order.Status.CANCELLED)
        self.assertEqual(Product.objects.get(pk=self.mat.pk).stock_quantity, 3)

    def test_admin_requires_permission(self):
        self.client.force_login(self.seller_user)
        self.assertNotEqual(self.client.get("/admin/shop_orders/").status_code, 200)
        self.client.force_login(self.staff)
        self.place(self.mat)
        self.client.force_login(self.staff)
        response = self.client.get("/admin/shop_orders/?show=open")
        self.assertContains(response, "سارا احمدی")

    def test_selling_settings_in_panel(self):
        self.client.force_login(self.seller_user)
        url = f"/fa/panel/{self.house_member.pk}/selling/"
        self.assertContains(self.client.get(url), "پرداخت به حساب خانه")
        self.client.post(url, {"account_holder": "ارموز", "bank_name": "", "card_number": "", "sheba": "ir۷۶ ۰۱۷۰ ۰۰۰۰ ۰۰۰۰ ۰۰۰۰ ۰۰۰۰ ۰۱",
                               "shipping_fee": "700000", "free_shipping_over": "", "prep_days": "2",
                               "shipping_note": "پست", "shipping_note_en": "", "order_mobile": "",
                               "order_email": "", "ship-TOTAL_FORMS": "0", "ship-INITIAL_FORMS": "0"})
        seller = Seller.objects.get(member=self.house_member)
        self.assertEqual((seller.shipping_fee, seller.mode), (700_000, Seller.Mode.HOUSE))
        self.assertEqual(seller.sheba, "IR760170000000000000000001")  # Persian digits and spaces normalised
        response = self.client.post(url, {"account_holder": "ارموز", "card_number": "6037991112345678",
                                          "sheba": "IR770170000000000000000001", "shipping_fee": "700000",
                                          "prep_days": "2", "order_mobile": "0912"})
        self.assertContains(response, "شماره کارت معتبر نیست")
        self.assertContains(response, "شماره شبا معتبر نیست")
        self.assertContains(response, "شماره موبایل باید ۱۱ رقم باشد")


@override_settings(DEBUG=True)
class OnlineOrderPaymentTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        config = PaymentSettings.load()
        config.enabled = True
        config.provider = "test"
        config.save()

    def test_pay_house_orders_online(self):
        self.add(self.mat)
        self.add(self.ring)
        self.checkout()
        purchase = Purchase.objects.get()
        page = self.client.get(f"/fa/shop/order/{purchase.code}/")
        self.assertContains(page, "پرداخت آنلاین")
        response = self.client.post(f"/fa/shop/order/{purchase.code}/", {"step": "pay_online"})
        payment = Payment.objects.get()
        self.assertEqual(payment.amount, 2_000_000 + 500_000)  # only the House order
        self.assertRedirects(response, f"/pay/{payment.uid}/test-gateway/", fetch_redirect_response=False)
        response = self.client.post(f"/pay/{payment.uid}/return/", {"result": "ok", "authority": payment.authority})
        self.assertRedirects(response, f"/fa/shop/order/{purchase.code}/?payment=ok", fetch_redirect_response=False)
        house = purchase.orders.get(member=self.house_member)
        self.assertEqual((house.status, house.paid_online), (Order.Status.PAID, True))
        self.assertEqual(purchase.orders.get(member=self.direct_member).status, Order.Status.AWAITING_PAYMENT)
        # coming back twice does not settle twice
        self.client.post(f"/pay/{payment.uid}/return/", {"result": "ok", "authority": payment.authority})
        self.assertEqual(house.events.filter(action="paid_online").count(), 1)
