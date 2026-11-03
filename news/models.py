"""
News, events and articles. Each language has its own news index page
(/fa/news/, /en/news/) and items are added under it in the page tree.
"""

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import models
from django.utils import timezone
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.search import index

from core.blocks import BodyBlock


class NewsKind(models.TextChoices):
    NEWS = "news", "خبر"
    EVENT = "event", "رویداد"
    ARTICLE = "article", "مقاله"


KIND_LABELS_EN = {"news": "News", "event": "Event", "article": "Article"}
KIND_PLURALS = {
    "news": ("اخبار", "News"),
    "event": ("رویدادها", "Events"),
    "article": ("مقاله‌ها", "Articles"),
}


class NewsIndexPage(Page):
    intro = models.TextField("خلاصه", blank=True)
    per_page = models.PositiveSmallIntegerField("تعداد مطلب در هر صفحه", default=12)

    content_panels = Page.content_panels + [FieldPanel("intro"), FieldPanel("per_page")]

    subpage_types = ["news.NewsPage"]
    max_count_per_parent = 1

    class Meta:
        verbose_name = "صفحه اخبار و رویدادها"

    def get_items(self):
        return NewsPage.objects.live().descendant_of(self).order_by("-date", "-first_published_at")

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        items = self.get_items()
        kind = request.GET.get("kind")
        if kind in NewsKind.values:
            items = items.filter(kind=kind)
        else:
            kind = ""
        paginator = Paginator(items, self.per_page or 12)
        try:
            page_obj = paginator.page(request.GET.get("page", 1))
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        today = timezone.localdate()
        context.update(
            items=page_obj,
            kind=kind,
            kinds=[(value, *KIND_PLURALS[value]) for value in NewsKind.values],
            upcoming_events=(
                self.get_items().filter(kind=NewsKind.EVENT, event_start__date__gte=today).order_by("event_start")[:3]
                if not kind and page_obj.number == 1 else []
            ),
        )
        return context


class NewsPage(Page):
    kind = models.CharField("نوع", max_length=10, choices=NewsKind.choices, default=NewsKind.NEWS)
    date = models.DateField("تاریخ انتشار", default=timezone.localdate)
    intro = models.TextField("خلاصه", blank=True, help_text="در فهرست اخبار و زیر عنوان نمایش داده می‌شود")
    cover_image = models.ForeignKey(
        "wagtailimages.Image", verbose_name="تصویر شاخص", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    body = StreamField(BodyBlock(), verbose_name="متن", blank=True)

    event_start = models.DateTimeField("زمان شروع رویداد", null=True, blank=True)
    event_end = models.DateTimeField("زمان پایان رویداد", null=True, blank=True)
    event_location = models.CharField("محل برگزاری", max_length=255, blank=True)
    event_registration_url = models.URLField("لینک ثبت‌نام", blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("kind"),
        FieldPanel("date"),
        FieldPanel("intro"),
        FieldPanel("cover_image"),
        FieldPanel("body"),
        MultiFieldPanel(
            [FieldPanel("event_start"), FieldPanel("event_end"), FieldPanel("event_location"),
             FieldPanel("event_registration_url")],
            heading="جزئیات رویداد (فقط برای رویدادها)",
        ),
    ]
    search_fields = Page.search_fields + [index.SearchField("intro"), index.SearchField("body")]

    class Meta:
        verbose_name = "خبر، رویداد یا مقاله"
        verbose_name_plural = "اخبار، رویدادها و مقاله‌ها"

    parent_page_types = ["news.NewsIndexPage"]
    subpage_types = []

    @property
    def kind_label(self):
        from core.models import is_english

        return KIND_LABELS_EN[self.kind] if is_english() else self.get_kind_display()

    @property
    def is_event(self):
        return self.kind == NewsKind.EVENT

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError

        if self.event_start and self.event_end and self.event_end < self.event_start:
            raise ValidationError({"event_end": "پایان رویداد نمی‌تواند پیش از شروع آن باشد."})
        if self.kind == NewsKind.EVENT and not self.event_start:
            raise ValidationError({"event_start": "برای رویداد، زمان شروع را وارد کنید."})

    @property
    def is_past_event(self):
        if not self.is_event or not self.event_start:
            return False
        return (self.event_end or self.event_start) < timezone.now()
