from django.core.validators import RegexValidator
from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable, Page
from wagtail.search import index

from core.blocks import BodyBlock

from .principles import ICON_CHOICES

HEX_COLOR = RegexValidator(r"^#[0-9a-fA-F]{6}$", "رنگ را به شکل #RRGGBB بنویسید، مثلاً #004e8f")


class StandardPage(Page):
    """A general content page: About, governance, how to buy, etc."""

    intro = models.TextField("خلاصه", blank=True)
    cover_image = models.ForeignKey(
        "wagtailimages.Image", verbose_name="تصویر سرصفحه", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    body = StreamField(BodyBlock(), verbose_name="متن", blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("cover_image"),
        FieldPanel("body"),
    ]
    search_fields = Page.search_fields + [index.SearchField("intro"), index.SearchField("body")]

    class Meta:
        verbose_name = "صفحه متنی"


class PrinciplesPage(Page):
    """The ten principles of fair trade, each editable on its own."""

    intro = RichTextField("مقدمه", blank=True)
    outro = RichTextField("متن پایانی", blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        InlinePanel("principles", label="اصول", min_num=1),
        FieldPanel("outro"),
    ]
    search_fields = Page.search_fields + [index.SearchField("intro")]
    max_count_per_parent = 1

    class Meta:
        verbose_name = "صفحه اصول ده‌گانه"


class Principle(Orderable):
    page = ParentalKey(PrinciplesPage, on_delete=models.CASCADE, related_name="principles")
    title = models.CharField("عنوان", max_length=120)
    description = models.TextField("توضیح", blank=True)
    colour = models.CharField(
        "رنگ", max_length=7, blank=True, validators=[HEX_COLOR],
        help_text="خالی بماند تا رنگ استاندارد WFTO برای این شماره به کار رود (مثلاً اصل ۱ آبی ‎#004e8f‎).",
    )
    icon_key = models.CharField(
        "آیکون", max_length=20, blank=True, choices=ICON_CHOICES,
        help_text="خالی بماند تا آیکون پیش‌فرض این شماره نمایش داده شود.",
    )
    icon = models.ForeignKey(
        "wagtailimages.Image", verbose_name="تصویر آیکون (اختیاری)", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        help_text="برای آیکون رسمی WFTO (پس از گرفتن اجازه از WFTO) یا هر آیکون دیگر؛ "
                  "مربع و با زمینه شفاف. جای آیکون پیش‌فرض را می‌گیرد.",
    )

    panels = [
        FieldPanel("title"), FieldPanel("description"),
        MultiFieldPanel([FieldPanel("colour"), FieldPanel("icon_key"), FieldPanel("icon")], heading="رنگ و آیکون"),
    ]
