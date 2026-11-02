from wagtail import blocks
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock


class ImageBlock(blocks.StructBlock):
    image = ImageChooserBlock(label="تصویر")
    caption = blocks.CharBlock(required=False, label="توضیح")

    class Meta:
        icon = "image"
        label = "تصویر"
        template = "core/blocks/image.html"


class QuoteBlock(blocks.StructBlock):
    text = blocks.TextBlock(label="متن")
    author = blocks.CharBlock(required=False, label="گوینده")

    class Meta:
        icon = "openquote"
        label = "نقل قول"
        template = "core/blocks/quote.html"


class CardBlock(blocks.StructBlock):
    title = blocks.CharBlock(label="عنوان")
    text = blocks.TextBlock(label="متن")

    class Meta:
        icon = "doc-full"
        label = "کارت"


class CardsBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False, label="عنوان بخش")
    cards = blocks.ListBlock(CardBlock(), label="کارت‌ها")

    class Meta:
        icon = "grip"
        label = "ردیف کارت‌ها"
        template = "core/blocks/cards.html"


class DocumentLinkBlock(blocks.StructBlock):
    document = DocumentChooserBlock(label="سند")
    title = blocks.CharBlock(required=False, label="عنوان نمایشی")

    class Meta:
        icon = "doc-full-inverse"
        label = "لینک سند"
        template = "core/blocks/document.html"


class BodyBlock(blocks.StreamBlock):
    heading = blocks.CharBlock(form_classname="title", icon="title", label="سرتیتر", template="core/blocks/heading.html")
    paragraph = blocks.RichTextBlock(icon="pilcrow", label="پاراگراف")
    image = ImageBlock()
    quote = QuoteBlock()
    cards = CardsBlock()
    document = DocumentLinkBlock()
    embed = EmbedBlock(icon="media", label="ویدیو یا رسانه")
