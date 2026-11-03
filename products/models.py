"""
Shop catalogue. In phase 1 there is no online payment: each product has a
"direct purchase" button that sends the buyer to the producer's own shop,
site or Instagram. Payment to the producer or to the house comes later.
"""

from django.db import models
from django.http import Http404
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel, ObjectList, TabbedInterface
from wagtail.contrib.routable_page.models import RoutablePageMixin, re_path
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.fields import RichTextField
from wagtail.models import Locale, Orderable, Page
from wagtail.search import index

from core.models import BilingualMixin, is_english
from members.models import Member, Region, paginate, querystring_without_page, unique_slug


class Category(BilingualMixin, models.Model):
    name = models.CharField("نام (فارسی)", max_length=80, unique=True)
    name_en = models.CharField("نام (انگلیسی)", max_length=80, blank=True)
    slug = models.SlugField("نشانی", max_length=80, unique=True, blank=True, allow_unicode=True)
    sort_order = models.PositiveSmallIntegerField("ترتیب نمایش", default=0)

    panels = [FieldPanel("name"), FieldPanel("name_en"), FieldPanel("slug"), FieldPanel("sort_order")]

    class Meta:
        verbose_name = "دسته‌بندی محصول"
        verbose_name_plural = "دسته‌بندی‌های محصول"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name_en or self.name)
        super().save(*args, **kwargs)


class Product(BilingualMixin, index.Indexed, ClusterableModel):
    member = models.ForeignKey(
        Member, verbose_name="تولیدکننده", on_delete=models.CASCADE, related_name="products",
    )
    category = models.ForeignKey(
        Category, verbose_name="دسته‌بندی", null=True, blank=True, on_delete=models.SET_NULL, related_name="products",
    )
    name = models.CharField("نام (فارسی)", max_length=160)
    name_en = models.CharField(
        "نام (انگلیسی)", max_length=160, blank=True,
        help_text="اگر خالی باشد، این محصول در نسخه انگلیسی سایت نمایش داده نمی‌شود",
    )
    slug = models.SlugField("نشانی صفحه", max_length=80, unique=True, blank=True, allow_unicode=True,
                            help_text="اگر خالی بماند خودکار ساخته می‌شود")
    summary = models.CharField("توضیح کوتاه (فارسی)", max_length=255, blank=True)
    summary_en = models.CharField("توضیح کوتاه (انگلیسی)", max_length=255, blank=True)
    description = RichTextField("توضیحات کامل (فارسی)", blank=True,
                                help_text="جنس، ابعاد، روش ساخت، سازندگان و داستان محصول")
    description_en = RichTextField("توضیحات کامل (انگلیسی)", blank=True)

    price = models.PositiveBigIntegerField("قیمت (ریال)", null=True, blank=True,
                                           help_text="اگر خالی باشد قیمت نمایش داده نمی‌شود")
    price_note = models.CharField("توضیح قیمت (فارسی)", max_length=120, blank=True,
                                  help_text="مثلاً «قیمت بر اساس سفارش» یا «هر کیلوگرم»")
    price_note_en = models.CharField("توضیح قیمت (انگلیسی)", max_length=120, blank=True)
    in_stock = models.BooleanField("موجود است", default=True)
    purchase_url = models.URLField(
        "لینک خرید مستقیم", blank=True,
        help_text="صفحه همین محصول در فروشگاه یا اینستاگرام تولیدکننده. اگر خالی باشد، "
                  "لینک وب‌سایت یا اینستاگرام تولیدکننده استفاده می‌شود.",
    )

    is_published = models.BooleanField("نمایش در سایت", default=True)
    needs_review = models.BooleanField(
        "در انتظار بررسی", default=False,
        help_text="محصولی که عضو از پنل اعضا ساخته؛ پس از بررسی، این تیک را بردارید تا در سایت نمایش داده شود",
    )
    is_featured = models.BooleanField("نمایش در صفحه اصلی", default=False)
    sort_order = models.PositiveSmallIntegerField("ترتیب نمایش", default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    search_fields = [
        index.SearchField("name"),
        index.SearchField("name_en"),
        index.SearchField("summary"),
        index.FilterField("is_published"),
    ]

    edit_handler = TabbedInterface([
        ObjectList([
            FieldRowPanel([FieldPanel("member"), FieldPanel("category")]),
            FieldPanel("name"),
            FieldPanel("slug"),
            FieldPanel("summary"),
            FieldPanel("description"),
            InlinePanel("images", label="تصاویر", heading="تصاویر محصول"),
        ], heading="فارسی و تصاویر"),
        ObjectList([
            FieldPanel("name_en"),
            FieldPanel("summary_en"),
            FieldPanel("description_en"),
            FieldPanel("price_note_en"),
        ], heading="انگلیسی"),
        ObjectList([
            MultiFieldPanel([
                FieldPanel("price"), FieldPanel("price_note"), FieldPanel("in_stock"),
            ], heading="قیمت و موجودی"),
            FieldPanel("purchase_url"),
            FieldPanel("is_published"),
            FieldPanel("needs_review"),
            FieldPanel("is_featured"),
            FieldPanel("sort_order"),
        ], heading="فروش و نمایش"),
    ])

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name_en or self.name)
        super().save(*args, **kwargs)

    @property
    def main_image(self):
        first = self.images.first()
        return first.image if first else None

    @property
    def direct_purchase_url(self):
        return self.purchase_url or self.member.purchase_url

    @classmethod
    def visible(cls):
        qs = (
            cls.objects.filter(is_published=True, needs_review=False, member__is_published=True)
            .exclude(member__status__in=Member.INACTIVE_STATUSES)
            .select_related("member", "category", "member__region")
            .prefetch_related("images__image")
        )
        if is_english():
            qs = qs.exclude(name_en="").exclude(member__name_en="")
        return qs

    def get_url(self):
        index_page = ProductIndexPage.for_active_locale()
        if index_page is None:
            return ""
        return index_page.url + index_page.reverse_subpage("product_detail", kwargs={"slug": self.slug})


class ProductImage(Orderable):
    product = ParentalKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ForeignKey("wagtailimages.Image", verbose_name="تصویر", on_delete=models.CASCADE, related_name="+")
    caption = models.CharField("توضیح تصویر", max_length=160, blank=True)

    panels = [FieldPanel("image"), FieldPanel("caption")]

    class Meta(Orderable.Meta):
        verbose_name = "تصویر محصول"
        verbose_name_plural = "تصاویر محصول"


@register_setting(icon="pick")
class ShopSettings(BaseGenericSetting):
    """Wording and behaviour of the shop, edited by the market development working group."""

    direct_purchase_label = models.CharField("متن دکمه خرید مستقیم (فارسی)", max_length=60, default="خرید از تولیدکننده")
    direct_purchase_label_en = models.CharField("متن دکمه خرید مستقیم (انگلیسی)", max_length=60, default="Buy from the producer")
    purchase_note = models.TextField(
        "توضیح خرید (فارسی)", blank=True,
        default="خرید فعلاً مستقیماً از خود تولیدکننده انجام می‌شود. با زدن دکمه خرید به صفحه فروش یا اینستاگرام تولیدکننده می‌روید.",
        help_text="زیر دکمه خرید در صفحه محصول نمایش داده می‌شود",
    )
    purchase_note_en = models.TextField(
        "توضیح خرید (انگلیسی)", blank=True,
        default="For now, purchases are made directly from the producer. The button takes you to the producer's own shop or Instagram page.",
    )
    show_prices = models.BooleanField("نمایش قیمت‌ها", default=True)
    show_prices_en = models.BooleanField(
        "نمایش قیمت ریالی در نسخه انگلیسی", default=False,
        help_text="برای خریداران خارجی معمولاً قیمت ریالی معنایی ندارد",
    )
    currency_label = models.CharField("واحد پول (فارسی)", max_length=20, default="ریال")
    currency_label_en = models.CharField("واحد پول (انگلیسی)", max_length=20, default="IRR")
    out_of_stock_label = models.CharField("متن ناموجود (فارسی)", max_length=40, default="ناموجود")
    out_of_stock_label_en = models.CharField("متن ناموجود (انگلیسی)", max_length=40, default="Out of stock")

    show_on_home = models.BooleanField("نمایش محصولات منتخب در صفحه اصلی", default=True)
    home_title = models.CharField("عنوان بخش در صفحه اصلی (فارسی)", max_length=120, default="محصولات اعضا")
    home_title_en = models.CharField("عنوان بخش در صفحه اصلی (انگلیسی)", max_length=120, default="Members' products")
    home_text = models.CharField("متن کوتاه بخش (فارسی)", max_length=255, blank=True)
    home_text_en = models.CharField("متن کوتاه بخش (انگلیسی)", max_length=255, blank=True)
    home_count = models.PositiveSmallIntegerField("تعداد محصولات در صفحه اصلی", default=8)
    per_page = models.PositiveSmallIntegerField("تعداد محصولات در هر صفحه فروشگاه", default=12)

    edit_handler = TabbedInterface([
        ObjectList([
            FieldPanel("direct_purchase_label"), FieldPanel("direct_purchase_label_en"),
            FieldPanel("purchase_note"), FieldPanel("purchase_note_en"),
        ], heading="خرید"),
        ObjectList([
            FieldPanel("show_prices"), FieldPanel("show_prices_en"),
            FieldPanel("currency_label"), FieldPanel("currency_label_en"),
            FieldPanel("out_of_stock_label"), FieldPanel("out_of_stock_label_en"),
        ], heading="قیمت"),
        ObjectList([
            FieldPanel("show_on_home"), FieldPanel("home_title"), FieldPanel("home_title_en"),
            FieldPanel("home_text"), FieldPanel("home_text_en"), FieldPanel("home_count"),
            FieldPanel("per_page"),
        ], heading="نمایش"),
    ])

    class Meta:
        verbose_name = "تنظیمات فروشگاه"

    def tr(self, field):
        return BilingualMixin.tr(self, field)

    @property
    def prices_visible(self):
        return self.show_prices and (self.show_prices_en or not is_english())


class ProductIndexPage(RoutablePageMixin, Page):
    """The shop: product list with filters, and each product's page as a sub-route."""

    intro = RichTextField("مقدمه", blank=True)

    content_panels = Page.content_panels + [FieldPanel("intro")]
    max_count_per_parent = 1
    subpage_types = []

    class Meta:
        verbose_name = "صفحه فروشگاه"

    @classmethod
    def for_active_locale(cls):
        return cls.objects.live().filter(locale=Locale.get_active()).first()

    @re_path(r"^$", name="product_list")
    def product_list(self, request):
        products = Product.visible()
        filters = {
            "category": request.GET.get("category", ""),
            "member": request.GET.get("member", ""),
            "region": request.GET.get("region", ""),
            "q": request.GET.get("q", "").strip(),
            "in_stock": request.GET.get("in_stock", ""),
        }
        if filters["category"]:
            products = products.filter(category__slug=filters["category"])
        if filters["member"]:
            products = products.filter(member__slug=filters["member"])
        if filters["region"].isdigit():
            products = products.filter(member__region_id=int(filters["region"]))
        if filters["in_stock"]:
            products = products.filter(in_stock=True)
        if filters["q"]:
            q = filters["q"]
            products = products.filter(
                models.Q(name__icontains=q) | models.Q(name_en__icontains=q)
                | models.Q(summary__icontains=q) | models.Q(summary_en__icontains=q)
                | models.Q(member__name__icontains=q) | models.Q(member__name_en__icontains=q)
            )

        visible = Product.visible()
        categories = Category.objects.filter(products__in=visible).distinct()
        producers = Member.objects.filter(products__in=visible).distinct()
        regions = Region.objects.filter(members__products__in=visible).distinct()
        if is_english():
            categories = categories.exclude(name_en="")
        shop = ShopSettings.load(request_or_site=request)
        return self.render(request, context_overrides={
            "products": paginate(request, products, shop.per_page),
            "filters": filters,
            "categories": categories,
            "producers": producers,
            "regions": regions,
            "querystring": querystring_without_page(request),
        })

    @re_path(r"^(?P<slug>[-\w]+)/$", name="product_detail")
    def product_detail(self, request, slug):
        product = Product.visible().filter(slug=slug).first()
        if product is None:
            raise Http404
        related = Product.visible().filter(member=product.member).exclude(pk=product.pk)[:4]
        return self.render(
            request,
            template="products/product_detail.html",
            context_overrides={
                "product": product,
                "related": related,
                "routable_suffix": self.reverse_subpage("product_detail", kwargs={"slug": slug}),
            },
        )
