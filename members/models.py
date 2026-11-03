"""
Member directory: the producers, institutions, networks and individuals who
belong to the house. Members are edited in the admin panel (Snippets → اعضا)
and shown on the members index page and its detail routes.
"""

from django.conf import settings
from django.core.paginator import Paginator
from django.db import models
from django.http import Http404
from django.utils.text import slugify
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, FieldRowPanel, MultiFieldPanel, ObjectList, TabbedInterface
from wagtail.contrib.routable_page.models import RoutablePageMixin, re_path
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.fields import RichTextField
from wagtail.models import Page
from wagtail.search import index

from core.models import BilingualMixin, is_english


def unique_slug(instance, source):
    """Build a slug from `source` that no other row of the same model uses."""
    base = slugify(source, allow_unicode=True)[:70] or "item"
    slug, n = base, 2
    qs = type(instance).objects.exclude(pk=instance.pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class Region(BilingualMixin, models.Model):
    """A province or area, used to filter members and products."""

    name = models.CharField("نام (فارسی)", max_length=80, unique=True)
    name_en = models.CharField("نام (انگلیسی)", max_length=80, blank=True)
    sort_order = models.PositiveSmallIntegerField("ترتیب نمایش", default=0)

    panels = [FieldPanel("name"), FieldPanel("name_en"), FieldPanel("sort_order")]

    class Meta:
        verbose_name = "منطقه"
        verbose_name_plural = "مناطق"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Member(BilingualMixin, index.Indexed, ClusterableModel):
    # Keys match the fee fields in core.models.MembershipSettings (application_fee_<key>).
    PRODUCER = "producer"
    INSTITUTION = "institution"
    NETWORK = "network"
    INDIVIDUAL = "individual"
    TYPE_CHOICES = [
        (PRODUCER, "تولیدکننده"),
        (INSTITUTION, "نهاد حمایتی"),
        (NETWORK, "شبکه تجارت عادلانه"),
        (INDIVIDUAL, "فرد حامی"),
    ]
    TYPE_LABELS_EN = {
        PRODUCER: "Producer",
        INSTITUTION: "Support institution",
        NETWORK: "Fair trade network",
        INDIVIDUAL: "Individual supporter",
    }

    TRIAL = "trial"
    OFFICIAL = "official"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (TRIAL, "عضو آزمایشی"),
        (OFFICIAL, "عضو رسمی"),
        (SUSPENDED, "تعلیق‌شده"),
        (CANCELLED, "عضویت لغوشده"),
    ]
    STATUS_LABELS_EN = {TRIAL: "Trial member", OFFICIAL: "Full member", SUSPENDED: "Suspended",
                        CANCELLED: "Membership cancelled"}
    # Not shown on the public site; no logo, services or panel editing (sections 1.7 and 1.8).
    INACTIVE_STATUSES = (SUSPENDED, CANCELLED)

    name = models.CharField("نام (فارسی)", max_length=160)
    name_en = models.CharField(
        "نام (انگلیسی)", max_length=160, blank=True,
        help_text="اگر خالی باشد، این عضو در نسخه انگلیسی سایت نمایش داده نمی‌شود",
    )
    slug = models.SlugField(
        "نشانی صفحه", max_length=80, unique=True, blank=True, allow_unicode=True,
        help_text="بخش پایانی نشانی صفحه عضو؛ اگر خالی بماند خودکار ساخته می‌شود",
    )
    member_type = models.CharField("نوع عضویت", max_length=20, choices=TYPE_CHOICES, default=PRODUCER)
    status = models.CharField("وضعیت عضویت", max_length=20, choices=STATUS_CHOICES, default=TRIAL)
    is_founding = models.BooleanField("عضو مؤسس", default=False)
    joined_on = models.DateField("تاریخ عضویت", null=True, blank=True)

    region = models.ForeignKey(
        Region, verbose_name="منطقه", null=True, blank=True, on_delete=models.SET_NULL, related_name="members",
    )
    city = models.CharField("شهر یا روستا (فارسی)", max_length=80, blank=True)
    city_en = models.CharField("شهر یا روستا (انگلیسی)", max_length=80, blank=True)

    summary = models.CharField("معرفی کوتاه (فارسی)", max_length=255, blank=True,
                               help_text="یک جمله برای کارت عضو در فهرست")
    summary_en = models.CharField("معرفی کوتاه (انگلیسی)", max_length=255, blank=True)
    story = RichTextField("داستان و معرفی کامل (فارسی)", blank=True)
    story_en = RichTextField("داستان و معرفی کامل (انگلیسی)", blank=True)

    logo = models.ForeignKey(
        "wagtailimages.Image", verbose_name="لوگو", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    cover_image = models.ForeignKey(
        "wagtailimages.Image", verbose_name="تصویر اصلی", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        help_text="عکس کارگاه، تولیدکنندگان یا محصولات؛ در کارت و بالای صفحه عضو",
    )

    instagram_url = models.URLField("اینستاگرام", blank=True)
    website_url = models.URLField("وب‌سایت یا فروشگاه اینترنتی", blank=True)
    public_phone = models.CharField("تلفن عمومی", max_length=40, blank=True)
    public_email = models.EmailField("ایمیل عمومی", blank=True)

    is_published = models.BooleanField("نمایش در سایت", default=True)
    is_featured = models.BooleanField("نمایش در صفحه اصلی", default=False)
    sort_order = models.PositiveSmallIntegerField("ترتیب نمایش", default=100,
                                                  help_text="عدد کوچک‌تر زودتر نمایش داده می‌شود")

    suspended_until = models.DateField(
        "پایان تعلیق", null=True, blank=True,
        help_text="با ثبت رأی تعلیق در «وضعیت اعضا» پر می‌شود؛ در این روز دبیرخانه برای رفع تعلیق یا لغو یادآوری می‌گیرد",
    )
    status_before_suspension = models.CharField(
        "وضعیت پیش از تعلیق", max_length=20, choices=STATUS_CHOICES[:2], blank=True,
        help_text="با رفع تعلیق، عضو به این وضعیت برمی‌گردد",
    )
    cancelled_on = models.DateField("تاریخ لغو عضویت", null=True, blank=True)
    reapply_after = models.DateField("امکان درخواست دوباره از", null=True, blank=True)

    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, verbose_name="کاربرانی که این عضو را مدیریت می‌کنند", blank=True,
        related_name="managed_members",
        help_text="برای پنل اعضا: این کاربران می‌توانند پروفایل و محصولات این عضو را ویرایش کنند",
    )

    application = models.OneToOneField(
        "membership.MembershipApplication", verbose_name="پرونده عضویت", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="member_profile",
        help_text="پرونده‌ای که این پروفایل از آن ساخته شده؛ وضعیت عضویت با تغییر وضعیت پرونده به‌روز می‌شود",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    search_fields = [
        index.SearchField("name"),
        index.SearchField("name_en"),
        index.SearchField("summary"),
        index.SearchField("summary_en"),
        index.FilterField("member_type"),
        index.FilterField("status"),
        index.FilterField("is_published"),
    ]

    edit_handler = TabbedInterface([
        ObjectList([
            FieldPanel("name"),
            FieldPanel("slug"),
            FieldRowPanel([FieldPanel("member_type"), FieldPanel("status")]),
            FieldRowPanel([FieldPanel("is_founding"), FieldPanel("joined_on")]),
            FieldRowPanel([FieldPanel("region"), FieldPanel("city")]),
            FieldPanel("summary"),
            FieldPanel("story"),
        ], heading="فارسی"),
        ObjectList([
            FieldPanel("name_en"),
            FieldPanel("city_en"),
            FieldPanel("summary_en"),
            FieldPanel("story_en"),
        ], heading="انگلیسی"),
        ObjectList([
            FieldPanel("logo"),
            FieldPanel("cover_image"),
            MultiFieldPanel([
                FieldPanel("instagram_url"), FieldPanel("website_url"),
                FieldPanel("public_phone"), FieldPanel("public_email"),
            ], heading="راه‌های ارتباط و خرید"),
        ], heading="تصاویر و لینک‌ها"),
        ObjectList([
            FieldPanel("is_published"),
            FieldPanel("is_featured"),
            FieldPanel("sort_order"),
            FieldPanel("managers"),
            FieldPanel("application"),
        ], heading="نمایش و دسترسی"),
        ObjectList([
            FieldPanel("suspended_until"),
            FieldPanel("status_before_suspension"),
            FieldPanel("cancelled_on"),
            FieldPanel("reapply_after"),
        ], heading="تعلیق و لغو",
            help_text="این‌ها را بهتر است از «وضعیت اعضا و حق عضویت» با ثبت رأی تغییر دهید تا ایمیل و سابقه ثبت شود"),
    ])

    class Meta:
        verbose_name = "عضو"
        verbose_name_plural = "اعضا"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name_en or self.name)
        super().save(*args, **kwargs)

    @property
    def type_label(self):
        return self.TYPE_LABELS_EN[self.member_type] if is_english() else self.get_member_type_display()

    @property
    def status_label(self):
        return self.STATUS_LABELS_EN[self.status] if is_english() else self.get_status_display()

    @property
    def is_trial(self):
        return self.status == self.TRIAL

    @property
    def is_inactive(self):
        return self.status in self.INACTIVE_STATUSES

    @property
    def purchase_url(self):
        """Where the "direct purchase" button sends buyers: the member's own shop or site, else Instagram."""
        return self.website_url or self.instagram_url

    @classmethod
    def visible(cls):
        """Members to show on the public site in the current language."""
        qs = cls.objects.filter(is_published=True).exclude(status__in=cls.INACTIVE_STATUSES).select_related("region", "logo", "cover_image")
        if is_english():
            qs = qs.exclude(name_en="")
        return qs

    def get_url(self):
        index_page = MemberIndexPage.for_active_locale()
        if index_page is None:
            return ""
        return index_page.url + index_page.reverse_subpage("member_detail", kwargs={"slug": self.slug})


@register_setting(icon="group")
class DirectorySettings(BaseGenericSetting):
    """How the member directory appears on the home page and index page."""

    show_on_home = models.BooleanField("نمایش اعضای منتخب در صفحه اصلی", default=True)
    home_title = models.CharField("عنوان بخش در صفحه اصلی (فارسی)", max_length=120, default="اعضای خانه")
    home_title_en = models.CharField("عنوان بخش در صفحه اصلی (انگلیسی)", max_length=120, default="Our members")
    home_text = models.CharField("متن کوتاه بخش (فارسی)", max_length=255, blank=True)
    home_text_en = models.CharField("متن کوتاه بخش (انگلیسی)", max_length=255, blank=True)
    home_count = models.PositiveSmallIntegerField("تعداد اعضا در صفحه اصلی", default=6)
    per_page = models.PositiveSmallIntegerField("تعداد اعضا در هر صفحه فهرست", default=12)
    show_trial_badge = models.BooleanField(
        "نشان «عضو آزمایشی» روی کارت اعضا نمایش داده شود", default=True,
        help_text="طبق سند ارکان، عضو آزمایشی حق استفاده از نشان خانه را ندارد",
    )

    panels = [
        MultiFieldPanel([
            FieldPanel("show_on_home"), FieldPanel("home_title"), FieldPanel("home_title_en"),
            FieldPanel("home_text"), FieldPanel("home_text_en"), FieldPanel("home_count"),
        ], heading="صفحه اصلی"),
        MultiFieldPanel([FieldPanel("per_page"), FieldPanel("show_trial_badge")], heading="فهرست اعضا"),
    ]

    class Meta:
        verbose_name = "تنظیمات فهرست اعضا"

    def tr(self, field):
        return BilingualMixin.tr(self, field)


def paginate(request, queryset, per_page):
    paginator = Paginator(queryset, max(per_page, 1))
    return paginator.get_page(request.GET.get("page"))


def querystring_without_page(request):
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


class MemberIndexPage(RoutablePageMixin, Page):
    """Lists members with filters; each member's profile is a sub-route of this page."""

    intro = RichTextField("مقدمه", blank=True)

    content_panels = Page.content_panels + [FieldPanel("intro")]
    max_count_per_parent = 1
    subpage_types = []

    class Meta:
        verbose_name = "صفحه فهرست اعضا"

    @classmethod
    def for_active_locale(cls):
        from wagtail.models import Locale

        return cls.objects.live().filter(locale=Locale.get_active()).first()

    def get_sitemap_urls(self, request=None):
        urls = super().get_sitemap_urls(request)
        base = self.get_full_url(request)
        english = self.locale.language_code == "en"
        for member in Member.visible():
            if english and not member.name_en:
                continue
            urls.append({
                "location": base + self.reverse_subpage("member_detail", kwargs={"slug": member.slug}),
                "lastmod": member.updated_at,
            })
        return urls

    @re_path(r"^$", name="member_list")
    def member_list(self, request):
        members = Member.visible()
        filters = {
            "type": request.GET.get("type", ""),
            "region": request.GET.get("region", ""),
            "status": request.GET.get("status", ""),
            "q": request.GET.get("q", "").strip(),
        }
        if filters["type"] in dict(Member.TYPE_CHOICES):
            members = members.filter(member_type=filters["type"])
        if filters["region"].isdigit():
            members = members.filter(region_id=int(filters["region"]))
        if filters["status"] == "founding":
            members = members.filter(is_founding=True)
        elif filters["status"] in (Member.TRIAL, Member.OFFICIAL):
            members = members.filter(status=filters["status"])
        if filters["q"]:
            q = filters["q"]
            members = members.filter(
                models.Q(name__icontains=q) | models.Q(name_en__icontains=q)
                | models.Q(summary__icontains=q) | models.Q(summary_en__icontains=q)
            )

        type_labels = Member.TYPE_LABELS_EN if is_english() else dict(Member.TYPE_CHOICES)
        regions = Region.objects.filter(members__in=Member.visible()).distinct()
        settings_obj = DirectorySettings.load(request_or_site=request)
        return self.render(request, context_overrides={
            "members": paginate(request, members, settings_obj.per_page),
            "filters": filters,
            "type_options": [(key, type_labels[key]) for key, _ in Member.TYPE_CHOICES],
            "regions": regions,
            "querystring": querystring_without_page(request),
            "directory_settings": settings_obj,
        })

    @re_path(r"^(?P<slug>[-\w]+)/$", name="member_detail")
    def member_detail(self, request, slug):
        member = Member.visible().filter(slug=slug).first()
        if member is None:
            raise Http404
        from products.models import Product

        return self.render(
            request,
            template="members/member_detail.html",
            context_overrides={
                "member": member,
                "products": Product.visible().filter(member=member),
                "routable_suffix": self.reverse_subpage("member_detail", kwargs={"slug": slug}),
                "directory_settings": DirectorySettings.load(request_or_site=request),
            },
        )
