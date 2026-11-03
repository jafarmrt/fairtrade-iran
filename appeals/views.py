"""Member panel pages for complaints and appeals, and the appeal attachment download."""

import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect

from contact.models import Complaint, notify_commission
from core.models import is_english
from memberpanel.views import member_view, render, t
from membership.jalali import parse_date

from . import notifications
from .forms import AppealForm, PanelComplaintForm
from .models import Appeal, AppealSettings


def _settings(request):
    return AppealSettings.load(request_or_site=request)


# ---- complaints ----

@member_view(editing=False)
def complaints(request, member):
    form = PanelComplaintForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = request.user
        with transaction.atomic():
            complaint = form.save(commit=False)
            complaint.member = member
            complaint.submitted_by = user
            complaint.name = user.get_full_name() or member.name
            complaint.email = user.email
            complaint.phone = member.public_phone
            complaint.relation = Complaint.Relation.MEMBER
            complaint.language = "en" if is_english() else "fa"
            complaint.save()
            transaction.on_commit(lambda: notify_commission(complaint))
        messages.success(request, t(f"شکایت شما با کد پیگیری {complaint.tracking_code} به کمیسیون نظارتی رسید.",
                                    f"Your complaint reached the Supervisory Commission. Tracking code: {complaint.tracking_code}."))
        return redirect("panel:complaints", member_id=member.pk)
    filed = Complaint.objects.filter(member=member, submitted_by=request.user)
    return render(request, "appeals/complaints.html", {
        "member": member, "form": form, "complaints": filed, "current": "complaints",
        "appeal_settings": _settings(request),
    })


# ---- appeals ----

@member_view(editing=False)
def appeals(request, member):
    return render(request, "appeals/appeal_list.html", {
        "member": member, "appeals": member.appeals.all(), "current": "appeals",
        "appeal_settings": _settings(request),
    })


@member_view(editing=False)
def appeal_new(request, member):
    settings = _settings(request)
    if not settings.enabled:
        raise Http404
    initial = {"email": request.user.email}
    if request.GET.get("decision") in Appeal.Decision.values:
        initial["decision"] = request.GET["decision"]
    if request.GET.get("body") in Appeal.Body.values:
        initial["decision_body"] = request.GET["body"]
    if parse_date(request.GET.get("date")):
        initial["decision_date"] = parse_date(request.GET["date"])
    form = AppealForm(request.POST or None, request.FILES or None, initial=initial,
                      window_days=settings.window_days)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            appeal = form.save(commit=False)
            appeal.member = member
            appeal.member_name = member.name
            appeal.submitted_by = request.user
            appeal.language = "en" if is_english() else "fa"
            appeal.save()
            transaction.on_commit(lambda: notifications.submitted(appeal))
        messages.success(request, t(
            f"اعتراض شما با کد پیگیری {appeal.tracking_code} به دبیر مجمع رسید.",
            f"Your appeal reached the Assembly Secretary. Tracking code: {appeal.tracking_code}.",
        ))
        return redirect("panel:appeals", member_id=member.pk)
    return render(request, "appeals/appeal_form.html", {
        "member": member, "form": form, "current": "appeals", "appeal_settings": settings,
    })


@login_required
def attachment(request, pk):
    """Appeal attachment: for the assembly secretary, or the managers of the member who appealed."""
    appeal = get_object_or_404(Appeal, pk=pk)
    is_owner = appeal.member_id and request.user.managed_members.filter(pk=appeal.member_id).exists()
    if not (request.user.has_perm("appeals.view_appeal") or is_owner):
        raise PermissionDenied
    if not appeal.attachment:
        raise Http404
    ext = os.path.splitext(appeal.attachment.name)[1]
    response = FileResponse(appeal.attachment.open("rb"), as_attachment=True,
                            filename=f"appeal-{appeal.tracking_code}{ext}")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
