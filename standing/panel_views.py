"""The member's page in the member panel: standing, annual dues and receipts."""

from django.contrib import messages
from django.shortcuts import redirect

from core.models import MembershipSettings
from memberpanel.views import member_view, membership_record, render, t

from .forms import ReceiptForm
from .models import Dues
from .services import StandingError, submit_receipt


@member_view(editing=False)
def membership(request, member):
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
        "decisions": member.decisions.all().order_by("-created_at"),
        "ms": MembershipSettings.load(request_or_site=request),
        "current": "membership",
        **membership_record(request, member),
    })
