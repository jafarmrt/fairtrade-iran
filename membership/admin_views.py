"""
Admin screens for the secretariat and the Supervisory Commission: a list of
membership files with deadlines, one page per file with its documents,
history and the actions the user's role allows, private file downloads and
a printable certificate.
"""

import mimetypes
import os

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from wagtail.admin.menu import MenuItem
from wagtail.admin.viewsets.base import ViewSet

from core.models import MembershipSettings, SiteSettings

from .forms import StaffActionForm
from .jalali import format_jalali
from .models import (
    CLOSED_STATUSES,
    ApplicationDocument,
    Certificate,
    MembershipApplication,
    MemberType,
    Status,
)
from .workflow import (
    COMMISSION,
    SECRETARIAT,
    WorkflowError,
    available_actions,
    blocking_reason,
    perform,
    user_roles,
)

VIEW_PERM = "membership.view_membershipapplication"


def require_view(request):
    if not request.user.has_perm(VIEW_PERM):
        raise PermissionDenied


def files_needing_action(user):
    """Open files whose next step belongs to one of the user's roles."""
    roles = user_roles(user)
    statuses = set()
    if SECRETARIAT in roles:
        statuses |= {Status.SUBMITTED, Status.APPROVED}
    if COMMISSION in roles:
        statuses |= {Status.COMMISSION, Status.TRIAL, Status.TRIAL_EXTENDED}
    if not statuses:
        return MembershipApplication.objects.none()
    return MembershipApplication.objects.filter(status__in=statuses).order_by("deadline")


def index(request):
    require_view(request)
    qs = MembershipApplication.objects.all().order_by("deadline", "-submitted_at")
    status = request.GET.get("status", "open")
    member_type = request.GET.get("type", "")
    q = request.GET.get("q", "").strip()
    if status == "open":
        qs = qs.exclude(status__in=CLOSED_STATUSES)
    elif status == "mine":
        qs = files_needing_action(request.user)
    elif status == "overdue":
        qs = qs.exclude(status__in=CLOSED_STATUSES).filter(deadline__lt=timezone.localdate())
    elif status in Status.values:
        qs = qs.filter(status=status)
    if member_type in MemberType.values:
        qs = qs.filter(member_type=member_type)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(name_en__icontains=q) | Q(tracking_code__icontains=q)
                       | Q(email__icontains=q) | Q(phone__icontains=q))
    status_filters = [("open", "پرونده‌های باز"), ("mine", "نیازمند اقدام من"), ("overdue", "گذشته از مهلت"),
                      ("all", "همه")] + list(Status.choices)
    return TemplateResponse(request, "membership/admin/index.html", {
        "page_title": "پرونده‌های عضویت",
        "header_icon": "group",
        "applications": qs[:500],
        "status": status,
        "member_type": member_type,
        "q": q,
        "status_filters": status_filters,
        "type_filters": MemberType.choices,
        "today": timezone.localdate(),
    })


def detail(request, pk):
    require_view(request)
    application = get_object_or_404(MembershipApplication, pk=pk)
    if request.method == "POST":
        form = StaffActionForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                perform(
                    application, data["action"], request.user,
                    message=data["message"], internal_note=data["internal_note"],
                    decision_reference=data["decision_reference"],
                    field_visit_date=data["field_visit_date"], field_visit_report=data["field_visit_report"],
                    request=request,
                )
            except WorkflowError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, "اقدام ثبت شد.")
                return redirect("membership_applications:detail", pk=application.pk)
        else:
            messages.error(request, "فرم اقدام درست پر نشده است.")
    actions = [
        {"action": a, "blocked": blocking_reason(application, a)}
        for a in available_actions(application, request.user)
    ]
    ms = MembershipSettings.load()
    return TemplateResponse(request, "membership/admin/detail.html", {
        "page_title": f"پرونده {application.tracking_code}",
        "page_subtitle": application.name,
        "header_icon": "group",
        "application": application,
        "documents": application.documents.all(),
        "events": application.events.select_related("user").order_by("-created_at"),
        "actions": actions,
        "roles": user_roles(request.user),
        "ms": ms,
        "certificate": application.certificate_or_none,
    })


def download(request, pk):
    require_view(request)
    document = get_object_or_404(ApplicationDocument, pk=pk)
    try:
        handle = document.file.open("rb")
    except FileNotFoundError:
        raise Http404
    name = document.original_name or os.path.basename(document.file.name)
    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    response = FileResponse(handle, as_attachment=True, filename=name, content_type=content_type)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


def certificate_context(certificate, lang):
    """What the printable certificate shows; also used by the member panel."""
    ms = MembershipSettings.load()
    site_settings = SiteSettings.load()
    is_en = lang == "en"
    from .models import MEMBER_TYPE_EN
    from .notifications import membership_page_url

    type_label = MEMBER_TYPE_EN.get(certificate.member_type) if is_en else certificate.get_member_type_display()
    name = (certificate.name_en or certificate.name) if is_en else certificate.name
    date = certificate.issued_on.strftime("%d %B %Y") if is_en else format_jalali(certificate.issued_on)
    text = (ms.certificate_text_en if is_en else ms.certificate_text) or ""
    text = text.replace("{name}", name).replace("{type}", type_label).replace("{date}", date)
    return {
        "certificate": certificate,
        "is_en": is_en,
        "name": name,
        "type_label": type_label,
        "date": date,
        "valid_until": (certificate.valid_until.strftime("%d %B %Y") if is_en else format_jalali(certificate.valid_until))
        if certificate.valid_until else "",
        "title": ms.certificate_title_en if is_en else ms.certificate_title,
        "text": text,
        "signatory": ms.certificate_signatory_en if is_en else ms.certificate_signatory,
        "signatory_title": ms.certificate_signatory_title_en if is_en else ms.certificate_signatory_title,
        "site_name": site_settings.site_name_en if is_en else site_settings.site_name,
        "logo": site_settings.logo_en if (is_en and site_settings.logo_en) else site_settings.logo,
        "check_url": membership_page_url(lang, f"certificate/?number={certificate.number}"),
    }


def certificate_print(request, pk):
    if not (request.user.has_perm(VIEW_PERM) or request.user.has_perm("membership.change_certificate")):
        raise PermissionDenied
    certificate = get_object_or_404(Certificate, pk=pk)
    lang = request.GET.get("lang", "fa")
    return TemplateResponse(request, "membership/admin/certificate_print.html", certificate_context(certificate, lang))


class ApplicationMenuItem(MenuItem):
    def is_shown(self, request):
        return request.user.has_perm(VIEW_PERM)


class ApplicationViewSet(ViewSet):
    name = "membership_applications"
    icon = "group"
    menu_label = "پرونده‌های عضویت"
    menu_order = 100

    def get_urlpatterns(self):
        return [
            path("", index, name="index"),
            path("<int:pk>/", detail, name="detail"),
            path("document/<int:pk>/", download, name="download"),
            path("certificate/<int:pk>/print/", certificate_print, name="certificate_print"),
        ]

    @property
    def menu_url(self):
        return reverse(self.get_url_name("index"))

    @property
    def menu_item_class(self):
        return ApplicationMenuItem
