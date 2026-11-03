"""
Admin: «وضعیت اعضا و حق عضویت». A list of accepted members with their dues
and standing, one page per member with dues, receipts and decisions, and a
staff-checked download of private receipts.
"""

import mimetypes
import os

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, OuterRef
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from wagtail.admin.menu import MenuItem
from wagtail.admin.viewsets.base import ViewSet

from core.iran import text_search
from core.models import MembershipSettings
from members.models import Member

from .forms import DecisionForm, StaffPaymentForm
from .models import Decision, Dues, DuesPayment
from .services import (
    SECRETARIAT,
    StandingError,
    available_kinds,
    can_view,
    decide,
    issue_by_hand,
    period_for,
    record_payment,
    review_payment,
    user_bodies,
    waive,
)


def _int(value):
    """A POSTed id, or 0 (no match, so a 404) when it is not a number."""
    return int(value) if str(value or "").isdigit() else 0


def require_view(request):
    if not can_view(request.user):
        raise PermissionDenied


def index(request):
    require_view(request)
    today = timezone.localdate()
    open_q = Dues.objects.filter(member=OuterRef("pk"), status__in=Dues.OPEN)
    overdue_q = Dues.objects.filter(member=OuterRef("pk"), status=Dues.Status.UNPAID, due_date__lt=today)
    pending_q = DuesPayment.objects.filter(dues__member=OuterRef("pk"), status=DuesPayment.Status.PENDING)
    qs = (Member.objects.annotate(owes=Exists(open_q), overdue=Exists(overdue_q), pending=Exists(pending_q),
                                  decision_count=Count("decisions"))
          .order_by("name"))
    show = request.GET.get("show", "all")
    q = request.GET.get("q", "").strip()
    filters = [
        ("all", "همه اعضا"),
        ("pending", "رسید در انتظار بررسی"),
        ("overdue", "گذشته از مهلت پرداخت"),
        ("owes", "حق عضویت پرداخت‌نشده"),
        ("suspended", "تعلیق‌شده"),
        ("ended", "مدت تعلیق تمام‌شده"),
        ("cancelled", "لغوشده"),
    ]
    if show == "pending":
        qs = qs.filter(pending=True)
    elif show == "overdue":
        qs = qs.filter(overdue=True)
    elif show == "owes":
        qs = qs.filter(owes=True)
    elif show == "suspended":
        qs = qs.filter(status=Member.SUSPENDED)
    elif show == "ended":
        qs = qs.filter(status=Member.SUSPENDED, suspended_until__lte=today)
    elif show == "cancelled":
        qs = qs.filter(status=Member.CANCELLED)
    if q:
        qs = qs.filter(text_search(q, "name", "name_en"))
    return TemplateResponse(request, "standing/admin/index.html", {
        "page_title": "وضعیت اعضا و حق عضویت",
        "header_icon": "user",
        "members": qs[:500],
        "show": show,
        "q": q,
        "filters": filters,
        "today": today,
        "pending_count": DuesPayment.objects.filter(status=DuesPayment.Status.PENDING).count(),
    })


def _act(request, member):
    """Handle one POSTed action on the member page. Returns an error message or ''."""
    bodies = user_bodies(request.user)
    action = request.POST.get("action", "")
    user = request.user
    if action == "decision":
        form = DecisionForm(request.POST, member=member, bodies=bodies)
        if not form.is_valid():
            return "؛ ".join(e for errors in form.errors.values() for e in errors)
        d = form.cleaned_data
        decide(member, d["kind"], d["reason"], user=user, message=d["message"], internal_note=d["internal_note"],
               decision_reference=d["decision_reference"], months=d["months"])
        return ""
    if SECRETARIAT not in bodies:
        raise PermissionDenied
    if action == "issue":
        issue_by_hand(member)
        return ""
    dues = get_object_or_404(member.dues.all(), pk=_int(request.POST.get("dues")))
    form = StaffPaymentForm(request.POST)
    form.is_valid()
    d = form.cleaned_data
    if action == "confirm" or action == "reject":
        payment = get_object_or_404(DuesPayment, pk=request.POST.get("payment"), dues=dues)
        review_payment(payment, user, confirm=(action == "confirm"), message=request.POST.get("message", ""))
    elif action == "record":
        if not d.get("amount"):
            return "مبلغ دریافتی را وارد کنید."
        record_payment(dues, user, d["amount"], reference=d.get("reference", ""), note=d.get("note", ""))
    elif action == "waive":
        waive(dues, user, note=d.get("note", ""))
    elif action == "warn":
        if dues.warned_on or not dues.is_open:
            return "اخطار این سال پیش‌تر فرستاده شده یا حق عضویت باز نیست."
        dues.warned_on = timezone.localdate()
        dues.save(update_fields=["warned_on"])
        decide(member, Decision.Kind.WARNING, Decision.Reason.DUES, user=user, body=SECRETARIAT, dues=dues,
               message=request.POST.get("message", ""))
    else:
        return "اقدام ناشناخته."
    return ""


def member_detail(request, pk):
    require_view(request)
    member = get_object_or_404(Member, pk=pk)
    bodies = user_bodies(request.user)
    if request.method == "POST":
        try:
            error = _act(request, member)
        except StandingError as e:
            error = str(e)
        if error:
            messages.error(request, error)
        else:
            messages.success(request, "ثبت شد.")
            return redirect("standing:member", pk=member.pk)
    ms = MembershipSettings.load()
    dues = list(member.dues.all().prefetch_related("payments__submitted_by", "payments__reviewed_by"))
    for d in dues:
        d.suspend_on = d.suspension_date(ms)
    current_year, _ = period_for(member, timezone.localdate(), ms)
    can_issue = not member.dues.filter(year=current_year).exists() and member.status != Member.CANCELLED
    decision_form = DecisionForm(member=member, bodies=bodies) if available_kinds(member, bodies) else None
    return TemplateResponse(request, "standing/admin/member.html", {
        "page_title": f"وضعیت عضو: {member.name}",
        "header_icon": "user",
        "member": member,
        "dues_list": dues,
        "decisions": member.decisions.select_related("created_by", "dues"),
        "decision_form": decision_form,
        "is_secretariat": SECRETARIAT in bodies,
        "bodies": bodies,
        "ms": ms,
        "today": timezone.localdate(),
        "annual_fee": ms.annual_fee_for(member.member_type),
        "can_issue": can_issue,
        "current_year": current_year,
        "certificate": member.application.certificate_or_none if member.application else None,
    })


def receipt_download(request, pk):
    require_view(request)
    payment = get_object_or_404(DuesPayment, pk=pk)
    if not payment.receipt:
        raise Http404
    try:
        handle = payment.receipt.open("rb")
    except FileNotFoundError:
        raise Http404
    name = payment.original_name or os.path.basename(payment.receipt.name)
    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    response = FileResponse(handle, as_attachment=True, filename=name, content_type=content_type)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


class StandingMenuItem(MenuItem):
    def is_shown(self, request):
        return can_view(request.user)


class StandingViewSet(ViewSet):
    name = "standing"
    icon = "user"
    menu_label = "وضعیت اعضا و حق عضویت"
    menu_order = 110

    def get_urlpatterns(self):
        return [
            path("", index, name="index"),
            path("member/<int:pk>/", member_detail, name="member"),
            path("receipt/<int:pk>/", receipt_download, name="receipt"),
        ]

    @property
    def menu_url(self):
        return reverse(self.get_url_name("index"))

    @property
    def menu_item_class(self):
        return StandingMenuItem
