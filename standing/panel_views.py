"""The member's page in the member panel: standing, annual dues and receipts."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from core.models import MembershipSettings
from memberpanel.views import member_view, membership_record, render, t

from .forms import ReceiptForm
from .models import Dues
from .services import StandingError, submit_receipt


def _int(value):
    """A POSTed id, or 0 (no match, so a 404) when it is not a number."""
    return int(value) if str(value or "").isdigit() else 0


@member_view(editing=False)
def membership(request, member):
    from payments.models import PaymentSettings
    from payments.services import online_enabled, start_payment

    online = online_enabled("dues")  # suspended members may pay too: paying lifts a suspension for unpaid dues
    if request.method == "POST" and request.POST.get("step") == "pay_dues":
        dues = get_object_or_404(member.dues.all(), pk=_int(request.POST.get("dues")))
        return start_payment(request, "dues", dues, reverse("panel:membership", kwargs={"member_id": member.pk}))
    form = ReceiptForm(request.POST or None, request.FILES or None, member=member)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            submit_receipt(data["dues"], request.user, data["amount"], reference=data["reference"],
                           paid_on_text=data["paid_on_text"], receipt=data["receipt"], note=data["note"])
        except StandingError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, t("رسید فرستاده شد. دبیرخانه پس از بررسی، پرداخت را تأیید می‌کند.",
                                        "Receipt sent. The secretariat will confirm the payment once it has checked it."))
            return redirect("panel:membership", member_id=member.pk)
    dues = member.dues.all().prefetch_related("payments")
    return render(request, "standing/panel_membership.html", {
        "member": member,
        "form": form,
        "dues_list": dues,
        "can_pay": member.dues.filter(status=Dues.Status.UNPAID).exists(),
        "online_dues": list(member.dues.filter(status=Dues.Status.UNPAID).order_by("year")) if online else [],
        "pay": PaymentSettings.load() if online else None,
        "payment_state": request.GET.get("payment"),
        "decisions": member.decisions.all().order_by("-created_at"),
        "ms": MembershipSettings.load(request_or_site=request),
        "current": "membership",
        **membership_record(request, member),
    })
