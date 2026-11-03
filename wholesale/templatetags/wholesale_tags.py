from django import template

register = template.Library()


@register.simple_tag
def wholesale_page():
    """The wholesale page in the active language, or None."""
    from wholesale.models import WholesalePage

    return WholesalePage.for_active_locale()
