"""
Online payment through an Iranian gateway (Zarinpal, IDPay, or a local test
gateway), for shop orders, the membership application fee and annual dues.

Off by default: it is switched on in the admin (Settings > پرداخت آنلاین) once
the House has an eNamad and a merchant account. Until then, and whenever a
gateway fails, people pay by bank transfer and upload a receipt as before.

Each thing that can be paid is a "purpose" (see purposes.py). An app starts a
payment with:

    from payments.services import online_enabled, start_payment
    if online_enabled("dues"):
        return start_payment(request, "dues", dues)
"""
