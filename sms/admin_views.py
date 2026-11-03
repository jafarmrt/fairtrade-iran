from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from wagtail.admin.menu import MenuItem
from wagtail.admin.viewsets.base import ViewSet

from .models import SmsLog, SmsSettings
from .phone import normalize_mobile
from .service import send_text

PERM = "sms.change_smssettings"


class TestForm(forms.Form):
    mobile = forms.CharField(label="شماره همراه", max_length=20)
    text = forms.CharField(label="متن", widget=forms.Textarea(attrs={"rows": 3}),
                           initial="پیامک آزمایشی سایت خانه تجارت عادلانه ایران")

    def clean_mobile(self):
        number = normalize_mobile(self.cleaned_data["mobile"])
        if not number:
            raise forms.ValidationError("شماره همراه معتبر نیست (مثلاً 09121234567).")
        return number


def index(request):
    if not request.user.has_perm(PERM):
        raise PermissionDenied
    config = SmsSettings.load(request_or_site=request)
    form = TestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        # A test is sent even while SMS is switched off, so the setup can be checked first.
        if send_text([form.cleaned_data["mobile"]], form.cleaned_data["text"], event="test", config=config):
            messages.success(request, "پیامک آزمایشی به سامانه پیامک تحویل شد.")
        else:
            last = SmsLog.objects.filter(event="test").first()
            messages.error(request, f"ارسال نشد: {last.error if last else 'خطای نامشخص'}")
        return redirect("sms_admin:index")
    return TemplateResponse(request, "sms/admin/index.html", {
        "page_title": "ارسال آزمایشی و گزارش پیامک",
        "header_icon": "mail",
        "config": config,
        "provider": config.get_provider_display(),
        "form": form,
        "logs": SmsLog.objects.all()[:200],
    })


class SmsMenuItem(MenuItem):
    def is_shown(self, request):
        return request.user.has_perm(PERM)


class SmsAdminViewSet(ViewSet):
    name = "sms_admin"
    icon = "mail"
    menu_label = "ارسال آزمایشی و گزارش"
    menu_order = 200

    def get_urlpatterns(self):
        return [path("", index, name="index")]

    @property
    def menu_url(self):
        return reverse(self.get_url_name("index"))

    @property
    def menu_item_class(self):
        return SmsMenuItem
