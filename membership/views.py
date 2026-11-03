"""Public views of the membership page (routes are declared on MembershipPage)."""

from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone

from core import throttle
from core.models import MembershipSettings, is_english

from . import notifications
from .forms import ApplicationForm, ResubmitForm, TrackForm
from .models import (
    WAITING_FOR_APPLICANT,
    ApplicationDocument,
    ApplicationEvent,
    Certificate,
    MembershipApplication,
    MemberType,
    member_type_label,
)
from .workflow import WorkflowError, applicant_resubmit, deadline_for

SESSION_DONE = "membership_done_code"
SESSION_TRACK = "membership_track_id"


def render(page, request, template, context=None, suffix=""):
    ctx = page.get_context(request)
    ctx["routable_suffix"] = suffix
    ctx.update(context or {})
    return TemplateResponse(request, template, ctx)


def member_types(page, ms):
    return [
        {
            "code": t.value,
            "label": member_type_label(t.value),
            "text": page.type_text(t.value),
            "application_fee": ms.application_fee_for(t.value),
            "annual_fee": ms.annual_fee_for(t.value),
        }
        for t in MemberType
    ]


def membership_index(page, request):
    ms = MembershipSettings.load()
    return render(page, request, "membership/membership_page.html", {
        "ms": ms,
        "member_types": member_types(page, ms),
        "steps": page.steps_with_values(),
    })


def apply(page, request, member_type):
    if member_type not in MemberType.values:
        raise Http404
    ms = MembershipSettings.load()
    suffix = f"apply/{member_type}/"
    is_en = is_english()
    ctx = {"ms": ms, "member_type": member_type, "member_type_label": member_type_label(member_type),
           "type_text": page.type_text(member_type)}
    if not ms.applications_open:
        return render(page, request, "membership/apply_closed.html", ctx, suffix)

    if request.method == "POST":
        if throttle.hit(request, "apply"):
            return throttle.throttled_response(request)
        form = ApplicationForm(request.POST, request.FILES, member_type=member_type, is_en=is_en, page=page)
        if form.is_valid():
            application = save_application(form, member_type, is_en, ms)
            transaction.on_commit(lambda: notifications.submitted(application, request=request))
            request.session[SESSION_DONE] = application.tracking_code
            return redirect(page.url + page.reverse_subpage("apply_done"))
    else:
        form = ApplicationForm(member_type=member_type, is_en=is_en, page=page)
    ctx.update({"form": form, "fee": form.fee})
    return render(page, request, "membership/apply.html", ctx, suffix)


@transaction.atomic
def save_application(form, member_type, is_en, ms):
    data = form.cleaned_data
    name, other_name = data["name"], data.get("name_en", "")
    if is_en:
        name_fa, name_en = (other_name or name), name
    else:
        name_fa, name_en = name, other_name
    application = MembershipApplication(
        member_type=member_type,
        language="en" if is_en else "fa",
        name=name_fa,
        name_en=name_en,
        contact_person=data.get("contact_person", ""),
        email=data["email"],
        phone=data["phone"],
        city=data.get("city", ""),
        address=data.get("address", ""),
        website=data.get("website", ""),
        referred_by=data.get("referred_by", ""),
        answers=form.answers(),
        fee_amount=form.fee or None,
        payment_reference=data.get("payment_reference", ""),
        agreed_principles=bool(data.get("agreed_principles")),
        agreed_inspections=bool(data.get("agreed_inspections")),
    )
    application.deadline = deadline_for(application.status, timezone.localdate(), ms, application)
    application.save()

    Kind = ApplicationDocument.Kind
    if data.get("receipt"):
        add_document(application, data["receipt"], Kind.RECEIPT, "رسید پرداخت هزینه درخواست")
    for question, upload in form.question_files():
        add_document(application, upload, Kind.ANSWER, question.label)
    for upload in data.get("documents") or []:
        add_document(application, upload, Kind.ADDITIONAL, "")
    ApplicationEvent.objects.create(application=application, action="submitted", to_status=application.status)
    return application


def add_document(application, upload, kind, label):
    return ApplicationDocument.objects.create(
        application=application, kind=kind, label=label or upload.name[:255],
        file=upload, original_name=upload.name[:255],
    )


def fee_payment_context(application):
    """Whether the applicant can pay the application fee online now."""
    from payments.models import PaymentSettings
    from payments.purposes import get as purpose
    from payments.services import online_enabled

    can = bool(application) and online_enabled("application_fee") and purpose("application_fee").can_pay(application)
    return {"fee_online": can, "pay": PaymentSettings.load() if can else None}


def apply_done(page, request):
    code = request.session.get(SESSION_DONE)
    if not code:
        return redirect(page.url)
    application = MembershipApplication.objects.filter(tracking_code=code).first()
    if request.method == "POST" and request.POST.get("step") == "pay_fee" and application:
        from payments.services import start_payment

        return start_payment(request, "application_fee", application, page.url + page.reverse_subpage("apply_done"))
    return render(page, request, "membership/apply_done.html", {
        "application": application, "payment_state": request.GET.get("payment"),
        **fee_payment_context(application),
    })


def track(page, request):
    is_en = is_english()
    application = None
    lookup_form = TrackForm(is_en=is_en)
    resubmit_form = None
    appeal_context = None
    error = ""

    session_id = request.session.get(SESSION_TRACK)
    if session_id:
        application = MembershipApplication.objects.filter(pk=session_id).first()

    if request.method == "POST" and request.POST.get("step") == "lookup":
        if throttle.hit(request, "lookup"):
            return throttle.throttled_response(request)
        lookup_form = TrackForm(request.POST, is_en=is_en)
        application = None
        request.session.pop(SESSION_TRACK, None)
        if lookup_form.is_valid():
            application = MembershipApplication.objects.filter(
                tracking_code=lookup_form.cleaned_data["code"],
                email__iexact=lookup_form.cleaned_data["email"],
            ).first()
            if application is None:
                error = ("No application matches this code and e-mail." if is_en
                         else "پرونده‌ای با این کد پیگیری و ایمیل پیدا نشد.")
            else:
                request.session[SESSION_TRACK] = application.pk
                return redirect(page.url + page.reverse_subpage("track"))
    elif request.method == "POST" and request.POST.get("step") == "resubmit" and application:
        resubmit_form = ResubmitForm(request.POST, request.FILES, is_en=is_en)
        if application.status in WAITING_FOR_APPLICANT and resubmit_form.is_valid():
            try:
                with transaction.atomic():
                    for upload in resubmit_form.cleaned_data["documents"]:
                        add_document(application, upload, ApplicationDocument.Kind.ADDITIONAL, "")
                    applicant_resubmit(application, resubmit_form.cleaned_data["message"], request=request)
            except WorkflowError as e:
                error = str(e)
            else:
                return redirect(page.url + page.reverse_subpage("track") + "?sent=1")
    elif request.method == "POST" and request.POST.get("step") == "appeal" and application:
        from appeals.applicant import submit

        appeal, appeal_context = submit(application, request.POST, request.FILES)
        if appeal is not None:
            return redirect(page.url + page.reverse_subpage("track") + "?appealed=1")
    elif request.method == "POST" and request.POST.get("step") == "pay_fee" and application:
        from payments.services import start_payment

        return start_payment(request, "application_fee", application, page.url + page.reverse_subpage("track"))
    elif request.method == "POST" and request.POST.get("step") == "logout":
        request.session.pop(SESSION_TRACK, None)
        return redirect(page.url + page.reverse_subpage("track"))

    if application and appeal_context is None:
        from appeals.applicant import tracking_context

        appeal_context = tracking_context(application)
    if application and application.status in WAITING_FOR_APPLICANT and resubmit_form is None:
        resubmit_form = ResubmitForm(is_en=is_en)
    return render(page, request, "membership/track.html", {
        "application": application,
        "lookup_form": lookup_form,
        "resubmit_form": resubmit_form if application and application.status in WAITING_FOR_APPLICANT else None,
        "error": error,
        "sent": request.GET.get("sent") == "1",
        "appealed": request.GET.get("appealed") == "1",
        "payment_state": request.GET.get("payment"),
        **fee_payment_context(application),
        **(appeal_context or {}),
    }, "track/")


def certificate_check(page, request):
    number = (request.GET.get("number") or "").strip().upper()
    certificate = None
    if number:
        certificate = Certificate.objects.filter(number__iexact=number).first()
    return render(page, request, "membership/certificate_check.html", {
        "number": number,
        "certificate": certificate,
        "searched": bool(number),
    }, "certificate/" + (f"?number={number}" if number else ""))
