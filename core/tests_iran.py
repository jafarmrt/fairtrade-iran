from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.utils import translation

from core import iran
from core.templatetags.site_tags import card_format, money, sheba_format
from membership.jalali import parse_date


class DigitsAndLettersTests(SimpleTestCase):
    def test_normalize_text(self):
        self.assertEqual(iran.normalize_text(" كاشي ۱۲٣ "), "کاشی 123")

    def test_search_variants(self):
        self.assertEqual(iran.search_variants("كيك"), ["کیک", "كيك"])
        self.assertEqual(iran.search_variants("rug"), ["rug"])


class MobileTests(SimpleTestCase):
    def test_forms_of_one_number(self):
        for value in ("09123456789", "۰۹۱۲۳۴۵۶۷۸۹", "+98 912 345 6789", "00989123456789", "9123456789",
                      "٠٩١٢٣٤٥٦٧٨٩"):
            self.assertEqual(iran.normalize_mobile(value), "09123456789", value)

    def test_rejects(self):
        for value in ("0912345678", "02188776655", "0912345678901", "۰۹۱۲abc"):
            self.assertEqual(iran.normalize_mobile(value), "", value)
        # Digits of other scripts are not accepted as if they were Latin.
        self.assertEqual(iran.normalize_mobile("09१२३४५६७८९"), "")

    def test_clean_mobile(self):
        self.assertEqual(iran.clean_mobile("۰۹۱۲ ۳۴۵ ۶۷۸۹"), "09123456789")
        with self.assertRaisesMessage(ValidationError, "۱۱ رقم"):
            iran.clean_mobile("0912")
        self.assertEqual(iran.clean_mobile("+44 7700 900123", allow_foreign=True), "+447700900123")
        with self.assertRaises(ValidationError):
            iran.clean_mobile("+44 1", english=True, allow_foreign=True)

    def test_same_phone(self):
        self.assertTrue(iran.same_phone("۰۹۱۲۳۴۵۶۷۸۹", "+989123456789"))
        self.assertFalse(iran.same_phone("09123456789", "09123456780"))


class IdentifierTests(SimpleTestCase):
    def test_national_id(self):
        for value in ("0499370899", "2914177763", "۲۹۱۴۱۷۷۷۶۳"):
            self.assertTrue(iran.is_national_id(value), value)
        for value in ("0499370898", "1111111111", "123", "29141777630"):
            self.assertFalse(iran.is_national_id(value), value)
        self.assertEqual(iran.clean_national_id("۰۴۹۹۳۷۰۸۹۹"), "0499370899")  # leading zero kept

    def test_legal_id(self):
        self.assertTrue(iran.is_legal_id("10380284790"))
        self.assertTrue(iran.is_legal_id("47577104656"))
        self.assertFalse(iran.is_legal_id("10380284791"))
        self.assertFalse(iran.is_legal_id("0499370899"))

    def test_postal_code(self):
        self.assertEqual(iran.clean_postal_code("۱۲۳۴۵-۶۷۸۹۰"), "1234567890")
        with self.assertRaisesMessage(ValidationError, "۱۰ رقم"):
            iran.clean_postal_code("12345")
        self.assertEqual(iran.clean_postal_code(""), "")

    def test_sheba(self):
        self.assertEqual(iran.clean_sheba("ir۷۶ ۰۱۷۰ ۰۰۰۰ ۰۰۰۰ ۰۰۰۰ ۰۰۰۰ ۰۱"), "IR760170000000000000000001")
        self.assertEqual(iran.clean_sheba("760170000000000000000001"), "IR760170000000000000000001")
        with self.assertRaisesMessage(ValidationError, "معتبر نیست"):
            iran.clean_sheba("IR770170000000000000000001")
        with self.assertRaisesMessage(ValidationError, "۲۴ رقم"):
            iran.clean_sheba("IR11")

    def test_card(self):
        self.assertEqual(iran.clean_card_number("۳۰۴۱-۱۴۴۲-۶۹۴۲-۰۸۰۹"), "3041144269420809")
        with self.assertRaisesMessage(ValidationError, "معتبر نیست"):
            iran.clean_card_number("3041144269420808")
        with self.assertRaisesMessage(ValidationError, "۱۶ رقم"):
            iran.clean_card_number("6037")

    def test_provinces(self):
        self.assertEqual(len(iran.PROVINCES), 31)
        self.assertIn(("تهران", "Tehran"), iran.province_choices(english=True))


class DisplayTests(SimpleTestCase):
    def test_money(self):
        with translation.override("fa"):
            self.assertEqual(money(12_450_000), "۱۲٬۴۵۰٬۰۰۰")
        with translation.override("en"):
            self.assertEqual(money(12_450_000), "12,450,000")

    def test_card_and_sheba(self):
        self.assertEqual(card_format("3041144269420809"), "3041 1442 6942 0809")
        self.assertEqual(sheba_format("IR760170000000000000000001"), "IR76 0170 0000 0000 0000 0000 01")


class JalaliParseTests(SimpleTestCase):
    def test_two_digit_year_is_refused(self):
        self.assertIsNone(parse_date("05/08/12"))
        self.assertIsNotNone(parse_date("۱۴۰۵/۰۸/۱۲"))
