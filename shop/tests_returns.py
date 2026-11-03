"""Shipping methods, printable invoices, returns and refunds, and the CSV exports and monthly report."""

import datetime

from django.utils import timezone

from core import exports
from core.models import SiteSettings
from products.models import Product, ShopSettings

from . import services
from .models import Order, Purchase, Seller, ShippingOption
from .tests import BUYER, ShopTestCase


class ShippingOptionTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        seller = Seller.objects.get(member=self.house_member)
        self.post = ShippingOption.objects.create(seller=seller, name="پست پیشتاز", name_en="Express post",
                                                  fee=600_000, sort_order=1)
        self.tipax = ShippingOption.objects.create(seller=seller, name="تیپاکس", name_en="Tipax", fee=900_000,
                                                   sort_order=2)
        ShippingOption.objects.create(seller=seller, name="غیرفعال", fee=1, active=False)

    def test_checkout_offers_the_methods_and_charges_the_chosen_one(self):
        self.add(self.mat)
        page = self.client.get("/fa/shop/checkout/")
        self.assertContains(page, "پست پیشتاز")
        self.assertContains(page, "تیپاکس")
        self.assertNotContains(page, "غیرفعال")
        self.checkout(**{f"ship_{self.house_member.pk}": self.tipax.pk})
        order = Purchase.objects.latest("created_at").orders.get()
        self.assertEqual((order.shipping, order.shipping_method, order.shipping_method_en), (900_000, "تیپاکس", "Tipax"))
        self.assertEqual(order.total, 2_000_000 + 900_000)

    def test_first_method_is_the_default_and_a_foreign_id_is_ignored(self):
        self.add(self.mat)
        other = ShippingOption.objects.create(seller=Seller.objects.get(member=self.direct_member), name="پیک",
                                              fee=10)
        self.checkout(**{f"ship_{self.house_member.pk}": other.pk})
        order = Purchase.objects.latest("created_at").orders.get()
        self.assertEqual((order.shipping, order.shipping_method), (600_000, "پست پیشتاز"))

    def test_free_shipping_threshold_still_applies(self):
        self.add(self.mat, 3)
        Seller.objects.filter(member=self.house_member).update(free_shipping_over=5_000_000)
        self.checkout(**{f"ship_{self.house_member.pk}": self.tipax.pk})
        order = Purchase.objects.latest("created_at").orders.get()
        self.assertEqual((order.shipping, order.shipping_method), (0, "تیپاکس"))

    def test_seller_edits_methods_in_the_panel(self):
        self.client.force_login(self.seller_user)
        url = f"/fa/panel/{self.house_member.pk}/selling/"
        self.assertContains(self.client.get(url), "روش‌های ارسال")
        data = {"account_holder": "ارموز", "shipping_fee": "500000", "prep_days": "2",
                "ship-TOTAL_FORMS": "4", "ship-INITIAL_FORMS": "3", "ship-MIN_NUM_FORMS": "0",
                "ship-MAX_NUM_FORMS": "1000"}
        for i, option in enumerate(ShippingOption.objects.filter(seller__member=self.house_member)):
            data.update({f"ship-{i}-id": option.pk, f"ship-{i}-name": option.name, f"ship-{i}-fee": option.fee,
                         f"ship-{i}-active": "on" if option.active else ""})
            if option == self.post:
                data[f"ship-{i}-DELETE"] = "on"
        data.update({"ship-3-name": "پیک تهران", "ship-3-fee": "۲۵۰۰۰۰", "ship-3-active": "on"})
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, response.content.decode()[:3000])
        names = set(ShippingOption.objects.filter(seller__member=self.house_member).values_list("name", flat=True))
        self.assertNotIn("پست پیشتاز", names)
        self.assertIn("پیک تهران", names)
        self.assertEqual(ShippingOption.objects.get(name="پیک تهران").fee, 250_000)


class InvoiceTests(ShopTestCase):
    def place(self):
        self.add(self.mat)
        self.checkout()
        return Purchase.objects.latest("created_at")

    def test_buyer_producer_and_staff_see_the_invoice(self):
        purchase = self.place()
        order = purchase.orders.get()
        url = f"/fa/shop/order/{purchase.code}/invoice/{order.pk}/"
        response = self.client.get(url)
        self.assertContains(response, order.code)
        self.assertContains(response, "حصیر")
        self.assertContains(response, BUYER["buyer_name"])
        self.assertContains(self.client.get(f"/fa/shop/order/{purchase.code}/"), url)
        self.assertContains(self.client.get(f"/en/shop/order/{purchase.code}/invoice/{order.pk}/"), "Invoice")

        self.client.logout()
        self.client.cookies.clear()
        self.assertEqual(self.client.get(url).status_code, 302)  # another visitor: order lookup first

        self.client.force_login(self.seller_user)
        self.assertContains(self.client.get(f"/fa/panel/{self.house_member.pk}/orders/{order.pk}/invoice/"),
                            order.code)
        self.client.force_login(self.direct_user)
        self.assertEqual(self.client.get(f"/fa/panel/{self.house_member.pk}/orders/{order.pk}/invoice/").status_code,
                         404)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(f"/admin/shop_orders/{order.pk}/invoice/"), order.code)

    def test_invoice_shows_jalali_date(self):
        purchase = self.place()
        order = purchase.orders.get()
        y, m, d = exports.jalali_today()
        response = self.client.get(f"/fa/shop/order/{purchase.code}/invoice/{order.pk}/")
        self.assertContains(response, str(y).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")))


class ReturnTests(ShopTestCase):
    def shipped(self, product=None):
        self.add(product or self.mat)
        self.checkout()
        purchase = Purchase.objects.latest("created_at")
        order = purchase.orders.get()
        services.confirm_payment(order, self.staff)
        services.ship(order, self.seller_user, "PST-1")
        return purchase, Order.objects.get(pk=order.pk)

    def test_buyer_requests_return_and_staff_refunds(self):
        purchase, order = self.shipped()
        self.assertEqual(Product.objects.get(pk=self.mat.pk).stock_quantity, 2)
        page = self.client.get(f"/fa/shop/order/{purchase.code}/")
        self.assertContains(page, "درخواست مرجوعی")
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/fa/shop/order/{purchase.code}/",
                             {"step": "return_request", "order": order.pk, "reason": "شکسته رسید"})
        order.refresh_from_db()
        self.assertEqual(order.return_reason, "شکسته رسید")
        self.assertIsNotNone(order.return_requested_at)
        # asking twice does nothing
        self.client.post(f"/fa/shop/order/{purchase.code}/", {"step": "return_request", "order": order.pk,
                                                              "reason": "دوباره"})
        order.refresh_from_db()
        self.assertEqual(order.return_reason, "شکسته رسید")

        self.client.force_login(self.staff)
        self.assertContains(self.client.get("/admin/shop_orders/?show=returns"), order.code)
        # the House received the money, so the producer cannot record the refund
        self.client.force_login(self.seller_user)
        self.client.post(f"/fa/panel/{self.house_member.pk}/orders/{order.pk}/", {"action": "refund"})
        self.assertEqual(Order.objects.get(pk=order.pk).status, Order.Status.SHIPPED)

        self.client.force_login(self.staff)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/admin/shop_orders/{order.pk}/", {
                "action": "refund", "refund_amount": "۲۰۰٬۰۰۰", "refund_reference": "RF-1", "restock": "1",
                "message": "مبلغ کالا برگشت داده شد"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.RETURNED)
        mode = SiteSettings.load().price_display
        self.assertEqual(order.refund_amount, 2_000_000 if mode != "rial" else 200_000)  # typed in toman
        self.assertEqual(order.refund_reference, "RF-1")
        self.assertEqual(Product.objects.get(pk=self.mat.pk).stock_quantity, 3)
        self.assertFalse(order.needs_settlement)

    def test_return_window_closes(self):
        purchase, order = self.shipped()
        Order.objects.filter(pk=order.pk).update(shipped_at=timezone.now() - datetime.timedelta(days=30))
        self.assertNotContains(self.client.get(f"/fa/shop/order/{purchase.code}/"), "ثبت درخواست مرجوعی")
        self.client.post(f"/fa/shop/order/{purchase.code}/", {"step": "return_request", "order": order.pk,
                                                              "reason": "دیر"})
        self.assertIsNone(Order.objects.get(pk=order.pk).return_requested_at)

    def test_producer_refunds_a_direct_order(self):
        self.add(self.ring)
        self.checkout()
        order = Purchase.objects.latest("created_at").orders.get()
        services.confirm_payment(order, self.direct_user, by=services.SELLER)
        self.client.force_login(self.direct_user)
        url = f"/fa/panel/{self.direct_member.pk}/orders/{order.pk}/"
        self.assertContains(self.client.get(url), "ثبت مرجوعی و بازپرداخت")
        self.client.post(url, {"action": "refund", "refund_amount": "", "message": "لغو با توافق"})
        order.refresh_from_db()
        self.assertEqual((order.status, order.refund_amount), (Order.Status.RETURNED, order.total))

    def test_refund_amount_cannot_exceed_total(self):
        _, order = self.shipped()
        with self.assertRaises(services.OrderError):
            services.refund(order, self.staff, order.total + 1)

    def test_return_days_zero_turns_returns_off(self):
        shop = ShopSettings.load()
        shop.return_days = 0
        shop.save()
        _, order = self.shipped()
        self.assertFalse(order.can_request_return())


class ExportTests(ShopTestCase):
    def test_orders_csv_and_monthly_report(self):
        self.add(self.mat)
        self.checkout()
        order = Purchase.objects.latest("created_at").orders.get()
        services.confirm_payment(order, self.staff)
        self.client.force_login(self.staff)
        response = self.client.get("/admin/shop_orders/?show=all&export=csv")
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        text = response.content.decode("utf-8")
        self.assertTrue(text.startswith("﻿"))
        self.assertIn(order.code, text)
        self.assertIn(exports.jalali_stamp(order.created_at, with_time=False), text)
        self.assertIn(",2500000,", text)  # amounts in rials, as plain numbers

        y, m, _ = exports.jalali_today()
        report = self.client.get("/admin/shop_orders/report/")
        self.assertContains(report, exports.month_name(m))
        self.assertContains(report, self.house_member.name)
        month_csv = self.client.get(f"/admin/shop_orders/report/?month={y}-{m:02d}&export=csv")
        self.assertIn(order.code, month_csv.content.decode())
        previous = "%d-%02d" % exports.add_months(y, m, -1)
        self.assertNotIn(order.code, self.client.get(f"/admin/shop_orders/report/?month={previous}&export=csv")
                         .content.decode())

    def test_exports_are_staff_only(self):
        self.client.force_login(self.seller_user)
        self.assertNotEqual(self.client.get("/admin/shop_orders/?export=csv").status_code, 200)
        self.assertNotEqual(self.client.get("/admin/shop_orders/report/").status_code, 200)


class JalaliMonthTests(ShopTestCase):
    def test_month_bounds(self):
        start, end = exports.month_bounds(1405, 1)
        self.assertEqual((start.date(), end.date()), (datetime.date(2026, 3, 21), datetime.date(2026, 4, 21)))
        start, end = exports.month_bounds(1404, 12)
        self.assertEqual(end.date(), datetime.date(2026, 3, 21))
        self.assertEqual(exports.add_months(1405, 1, -1), (1404, 12))
        self.assertEqual(exports.add_months(1405, 12, 1), (1406, 1))
        self.assertEqual(exports.parse_month("۱۴۰۵/۰۸"), (1405, 8))
        self.assertIsNone(exports.parse_month("1405-13"))
        self.assertEqual(exports.jalali_stamp(datetime.date(2026, 11, 3)), "1405/08/12")
