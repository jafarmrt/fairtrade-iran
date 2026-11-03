from functools import wraps

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from wagtail.images import get_image_model
from wagtail.log_actions import log
from wagtail.models import Collection

from core.models import SiteSettings, is_english
from members.models import Member
from products.models import Product, ProductImage

from .forms import PanelPasswordResetForm, ProductForm, ProfileForm
from .models import PanelSettings
from .onboarding import notify_product_review

UPLOAD_COLLECTION = "تصاویر اعضا"
LOGIN_URL = reverse_lazy("panel:login")


def t(fa, en):
    return en if is_english() else fa


def upload_collection():
    root = Collection.get_first_root_node()
    collection = root.get_children().filter(name=UPLOAD_COLLECTION).first()
    return collection or root.add_child(name=UPLOAD_COLLECTION)


def save_image(upload, title, user):
    image = get_image_model()(title=title[:255], file=upload, collection=upload_collection(),
                              uploaded_by_user=user)
    image.save()
    return image


def panel_enabled(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not PanelSettings.load(request_or_site=request).enabled:
            return TemplateResponse(request, "memberpanel/closed.html", status=503)
        return view(request, *args, **kwargs)
    return wrapper


def member_view(editing=True):
    """Login required; loads the member from the URL among the ones this user manages."""

    def decorator(view):
        @panel_enabled
        @login_required(login_url=LOGIN_URL)
        @wraps(view)
        def wrapper(request, member_id, *args, **kwargs):
            member = get_object_or_404(request.user.managed_members.all(), pk=member_id)
            if editing and member.status == Member.SUSPENDED:
                messages.error(request, t("عضویت این مجموعه تعلیق شده و ویرایش آن ممکن نیست.",
                                          "This membership is suspended, so it cannot be edited."))
                return redirect("panel:dashboard")
            return view(request, member, *args, **kwargs)
        return wrapper
    return decorator


def render(request, template, context):
    context.setdefault("panel_settings", PanelSettings.load(request_or_site=request))
    return TemplateResponse(request, template, context)


# ---- dashboard ----

@panel_enabled
@login_required(login_url=LOGIN_URL)
def dashboard(request):
    members = list(request.user.managed_members.all().select_related("logo", "region"))
    for member in members:
        products = member.products.all()
        member.panel_counts = {
            "total": products.count(),
            "live": products.filter(is_published=True, needs_review=False).count(),
            "review": products.filter(needs_review=True).count(),
        }
        member.public_url = member.get_url() if member.is_published and member.status != Member.SUSPENDED else ""
    return render(request, "memberpanel/dashboard.html", {"members": members, "current": "dashboard"})


# ---- profile ----

@member_view()
def profile(request, member):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=member)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            member = form.save(commit=False)
            form.apply_rich_fields(member)
            if form.cleaned_data.get("remove_logo"):
                member.logo = None
            if form.cleaned_data.get("remove_cover"):
                member.cover_image = None
            if form.cleaned_data.get("logo_upload"):
                member.logo = save_image(form.cleaned_data["logo_upload"], f"{member.name} - لوگو", request.user)
            if form.cleaned_data.get("cover_upload"):
                member.cover_image = save_image(form.cleaned_data["cover_upload"], member.name, request.user)
            member.save()
            log(instance=member, action="wagtail.edit", user=request.user)
        messages.success(request, t("پروفایل ذخیره شد.", "Your profile was saved."))
        return redirect("panel:profile", member_id=member.pk)
    return render(request, "memberpanel/profile.html", {"member": member, "form": form, "current": "profile"})


# ---- products ----

@member_view(editing=False)
def product_list(request, member):
    products = member.products.all().select_related("category").prefetch_related("images__image")
    settings = PanelSettings.load(request_or_site=request)
    can_add = member.status != Member.SUSPENDED and (
        not settings.max_products or products.count() < settings.max_products)
    return render(request, "memberpanel/product_list.html",
                  {"member": member, "products": products, "can_add": can_add, "current": "products"})


def _save_product(request, member, form, product, settings):
    is_new = product.pk is None
    with transaction.atomic():
        product = form.save(commit=False)
        product.member = member
        form.apply_rich_fields(product)
        if is_new and settings.new_products_need_review:
            product.needs_review = True
        product.save()
        remove_ids = [int(i) for i in request.POST.getlist("remove_image") if i.isdigit()]
        if remove_ids:
            product.images.filter(pk__in=remove_ids).delete()
        start = (product.images.order_by("-sort_order").values_list("sort_order", flat=True).first() or 0) + 1
        for n, upload in enumerate(form.cleaned_data.get("new_images") or []):
            image = save_image(upload, product.name, request.user)
            ProductImage.objects.create(product=product, image=image, sort_order=start + n)
        log(instance=product, action="wagtail.create" if is_new else "wagtail.edit", user=request.user)
        if is_new and product.needs_review:
            transaction.on_commit(lambda: notify_product_review(product))
    return product, is_new


@member_view()
def product_add(request, member):
    settings = PanelSettings.load(request_or_site=request)
    if settings.max_products and member.products.count() >= settings.max_products:
        messages.error(request, t("به بیشترین تعداد محصول مجاز رسیده‌اید.", "You have reached the product limit."))
        return redirect("panel:products", member_id=member.pk)
    product = Product(member=member)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product,
                       max_images=settings.max_images_per_product)
    if request.method == "POST" and form.is_valid():
        product, _ = _save_product(request, member, form, product, settings)
        if product.needs_review:
            messages.success(request, t("محصول ثبت شد و پس از بررسی دبیرخانه در سایت نمایش داده می‌شود.",
                                        "Product saved. It will appear on the website once the secretariat has reviewed it."))
        else:
            messages.success(request, t("محصول ثبت شد.", "Product saved."))
        return redirect("panel:products", member_id=member.pk)
    return render(request, "memberpanel/product_form.html", {"member": member, "form": form, "product": None, "current": "products"})


@member_view()
def product_edit(request, member, product_id):
    product = get_object_or_404(member.products.all(), pk=product_id)
    settings = PanelSettings.load(request_or_site=request)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product,
                       max_images=settings.max_images_per_product)
    if request.method == "POST" and form.is_valid():
        _save_product(request, member, form, product, settings)
        messages.success(request, t("محصول ذخیره شد.", "Product saved."))
        return redirect("panel:products", member_id=member.pk)
    return render(request, "memberpanel/product_form.html", {
        "member": member, "form": form, "product": product, "current": "products",
        "images": product.images.all().select_related("image"),
        "public_url": product.get_url() if product in Product.visible() else "",
    })


@member_view()
def product_delete(request, member, product_id):
    settings = PanelSettings.load(request_or_site=request)
    if not settings.allow_delete_products:
        raise Http404
    product = get_object_or_404(member.products.all(), pk=product_id)
    if request.method == "POST":
        log(instance=product, action="wagtail.delete", user=request.user)
        product.delete()
        messages.success(request, t("محصول حذف شد.", "Product deleted."))
        return redirect("panel:products", member_id=member.pk)
    return render(request, "memberpanel/product_delete.html", {"member": member, "product": product, "current": "products"})


# ---- accounts ----

class LoginView(auth_views.LoginView):
    template_name = "memberpanel/registration/login.html"
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        if not PanelSettings.load(request_or_site=request).enabled:
            return TemplateResponse(request, "memberpanel/closed.html", status=503)
        return super().dispatch(request, *args, **kwargs)

    def get_default_redirect_url(self):
        return reverse("panel:dashboard")


class LogoutView(auth_views.LogoutView):
    def get_success_url(self):
        return reverse("panel:login")


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "memberpanel/registration/password_reset.html"
    email_template_name = "memberpanel/registration/password_reset_email.txt"
    subject_template_name = "memberpanel/registration/password_reset_subject.txt"
    success_url = reverse_lazy("panel:password_reset_done")
    form_class = PanelPasswordResetForm

    def form_valid(self, form):
        self.extra_email_context = {"IS_EN": is_english(),
                                    "site_name": SiteSettings.load(request_or_site=self.request).tr("site_name")}
        return super().form_valid(form)


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "memberpanel/registration/message.html"
    extra_context = {"message_key": "reset_sent"}


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "memberpanel/registration/password_set.html"
    success_url = reverse_lazy("panel:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "memberpanel/registration/message.html"
    extra_context = {"message_key": "reset_complete"}


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "memberpanel/registration/password_set.html"
    success_url = reverse_lazy("panel:dashboard")
    extra_context = {"current": "password", "change": True}

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path(), LOGIN_URL)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, t("رمز عبور شما تغییر کرد.", "Your password was changed."))
        return super().form_valid(form)


# ---- membership file and certificate ----

APPEALABLE_STATUSES = {"rejected": "rejection", "not_accepted": "rejection"}


@member_view(editing=False)
def membership_file(request, member):
    import datetime

    from django.utils import timezone

    from appeals.models import AppealSettings

    application = member.application
    certificate = application.certificate_or_none if application else None
    events = []
    appeal_settings = AppealSettings.load(request_or_site=request)
    if application:
        cutoff = timezone.localdate() - datetime.timedelta(days=appeal_settings.window_days)
        for event in application.public_events():
            day = timezone.localtime(event.created_at).date()
            event.appeal_decision = (
                APPEALABLE_STATUSES.get(event.to_status, "")
                if appeal_settings.enabled and day >= cutoff else ""
            )
            event.day = day
            events.append(event)
    return render(request, "memberpanel/membership_file.html", {
        "member": member, "application": application, "certificate": certificate, "events": events,
        "appeals": member.appeals.all()[:5], "current": "file",
    })


@member_view(editing=False)
def certificate(request, member):
    from membership.admin_views import certificate_context

    cert = member.application.certificate_or_none if member.application else None
    if cert is None or cert.revoked:
        raise Http404
    context = certificate_context(cert, "en" if is_english() else "fa")
    return TemplateResponse(request, "membership/admin/certificate_print.html", context)
