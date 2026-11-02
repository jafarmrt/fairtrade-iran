"""
The document archive: a document model with English title and description,
and a page that lists documents collection by collection, showing each
visitor only the collections they are allowed to open.
"""

from django.conf import settings
from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.documents.models import AbstractDocument
from wagtail.documents.models import Document as WagtailDocument
from wagtail.models import Orderable, Page

from core.models import BilingualMixin

from .storage import private_document_storage


class ArchiveDocument(BilingualMixin, AbstractDocument):
    file = models.FileField(upload_to="", storage=private_document_storage, verbose_name="فایل")
    title_en = models.CharField(
        "عنوان انگلیسی", max_length=255, blank=True,
        help_text="اگر خالی باشد، سند در نسخه انگلیسی سایت فهرست نمی‌شود",
    )
    description = models.TextField("توضیح", blank=True)
    description_en = models.TextField("توضیح انگلیسی", blank=True)
    document_date = models.DateField("تاریخ سند", null=True, blank=True,
                                     help_text="مثلاً تاریخ تصویب یا انتشار؛ برای مرتب‌سازی فهرست")

    admin_form_fields = WagtailDocument.admin_form_fields + (
        "title_en", "description", "description_en", "document_date",
    )

    class Meta(AbstractDocument.Meta):
        verbose_name = "سند"
        verbose_name_plural = "اسناد"

    @property
    def has_english(self):
        return bool(self.title_en)


class DocumentsPage(Page):
    intro = models.TextField("خلاصه", blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        InlinePanel("sections", label="بخش‌ها", min_num=1,
                    help_text="هر بخش اسناد یک مجموعه را نشان می‌دهد. دسترسی هر مجموعه از «تنظیمات > مجموعه‌ها» تعیین می‌شود."),
    ]
    max_count_per_parent = 1

    class Meta:
        verbose_name = "صفحه اسناد"

    def get_context(self, request, *args, **kwargs):
        from core.models import is_english

        context = super().get_context(request, *args, **kwargs)
        english = is_english()
        sections = []
        for section in self.sections.select_related("collection"):
            if section.collection_id is None:
                continue
            allowed = section.user_can_view(request)
            if not allowed and not section.show_when_locked:
                continue
            documents = section.get_documents(request)
            if english:
                documents = documents.exclude(title_en="")
            sections.append({
                "section": section,
                "allowed": allowed,
                "documents": list(documents) if allowed else [],
            })
        context["sections"] = sections
        context["login_url"] = settings.LOGIN_URL
        return context


class DocumentsSection(Orderable):
    page = ParentalKey(DocumentsPage, on_delete=models.CASCADE, related_name="sections")
    heading = models.CharField("عنوان بخش", max_length=200)
    description = models.TextField("توضیح", blank=True)
    collection = models.ForeignKey(
        "wagtailcore.Collection", verbose_name="مجموعه", null=True, on_delete=models.SET_NULL, related_name="+",
    )
    include_subcollections = models.BooleanField("اسناد زیرمجموعه‌ها هم نمایش داده شود", default=True)
    show_when_locked = models.BooleanField(
        "برای کسانی که دسترسی ندارند هم نمایش داده شود", default=False,
        help_text="اگر روشن باشد، بازدیدکننده بدون دسترسی عنوان بخش و پیام «نیاز به ورود» را می‌بیند؛ "
                  "اگر خاموش باشد، بخش برای او کاملاً پنهان است.",
    )

    panels = [
        FieldPanel("heading"), FieldPanel("description"), FieldPanel("collection"),
        FieldPanel("include_subcollections"), FieldPanel("show_when_locked"),
    ]

    def user_can_view(self, request, collection=None):
        collection = collection or self.collection
        return all(r.accept_request(request) for r in collection.get_view_restrictions())

    def get_documents(self, request):
        """Documents of this collection (and its subcollections) that the visitor may open."""
        if self.include_subcollections:
            collections = [
                c for c in self.collection.get_descendants(inclusive=True)
                if c.pk == self.collection_id or self.user_can_view(request, c)
            ]
        else:
            collections = [self.collection]
        return ArchiveDocument.objects.filter(collection__in=collections).order_by(
            models.F("document_date").desc(nulls_last=True), "-created_at",
        )
