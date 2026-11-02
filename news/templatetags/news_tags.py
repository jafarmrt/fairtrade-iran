from django import template
from wagtail.models import Locale

from news.models import NewsPage

register = template.Library()


@register.simple_tag
def latest_news(count=3):
    """The newest live news items in the current language (for the home page)."""
    return NewsPage.objects.live().filter(locale=Locale.get_active()).order_by("-date", "-first_published_at")[:count]
