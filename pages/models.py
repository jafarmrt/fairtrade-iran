from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable, Page
from wagtail.search import index

from core.blocks import BodyBlock


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

    panels = [FieldPanel("title"), FieldPanel("description")]
