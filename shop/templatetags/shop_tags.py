from django import template

from products.models import ProductIndexPage, ShopSettings

from ..cart import SESSION_KEY

register = template.Library()


@register.simple_tag(takes_context=True)
def cart_link(context):
    """(url, count) for the header's cart link, or None when the cart is empty or off."""
    request = context.get("request")
    if request is None or not hasattr(request, "session"):
        return None
    count = sum(int(v) for v in (request.session.get(SESSION_KEY) or {}).values())
    if not count or not ShopSettings.load(request_or_site=request).cart_active:
        return None
    page = ProductIndexPage.for_active_locale()
    if page is None:
        return None
    return {"url": page.url + page.reverse_subpage("cart"), "count": count}


@register.simple_tag(takes_context=True)
def shop_url(context, name, **kwargs):
    page = ProductIndexPage.for_active_locale()
    if page is None:
        return ""
    return page.url + page.reverse_subpage(name, kwargs=kwargs or None)
