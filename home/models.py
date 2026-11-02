from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, PageChooserPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page

from core.blocks import BodyBlock


class HomePage(Page):
    hero_title = models.CharField("عنوان اصلی", max_length=200, blank=True)
    hero_text = models.TextField("متن معرفی کوتاه", blank=True)
    hero_image = models.ForeignKey(
        "wagtailimages.Image", verbose_name="تصویر اصلی", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    hero_cta_text = models.CharField("متن دکمه اصلی", max_length=60, blank=True)
    hero_cta_page = models.ForeignKey(
        "wagtailcore.Page", verbose_name="صفحه دکمه اصلی", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    intro = RichTextField("معرفی", blank=True)
    body = StreamField(BodyBlock(), verbose_name="بخش‌های بیشتر", blank=True)

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [FieldPanel("hero_title"), FieldPanel("hero_text"), FieldPanel("hero_image"),
             FieldPanel("hero_cta_text"), PageChooserPanel("hero_cta_page")],
            heading="بخش بالای صفحه",
        ),
        FieldPanel("intro"),
        FieldPanel("body"),
    ]

    max_count_per_parent = 1

    class Meta:
        verbose_name = "صفحه اصلی"
