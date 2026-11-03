from django import template
from django.utils.safestring import mark_safe

from pages import principles

register = template.Library()


@register.inclusion_tag("pages/includes/principle_badge.html")
def principle_badge(principle, number):
    """The coloured tile with the principle's icon: an uploaded icon if there is one, else a built-in one."""
    colour = principle.colour or principles.default_colour(number)
    key = principle.icon_key or principles.default_icon(number)
    return {
        "colour": colour,
        "ink": principles.ink_for(colour),
        "image": principle.icon,
        "svg": mark_safe(principles.ICONS[key][1]),
    }


@register.simple_tag
def principle_colour(principle, number):
    return principle.colour or principles.default_colour(number)


@register.filter
def fa_digits(value):
    from core.jalali import to_persian_digits
    return to_persian_digits(str(value))
