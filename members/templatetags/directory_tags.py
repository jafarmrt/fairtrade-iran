from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def featured_members(context):
    from members.models import DirectorySettings, Member

    conf = DirectorySettings.load(request_or_site=context.get("request"))
    if not conf.show_on_home:
        return []
    members = Member.visible().filter(is_featured=True)
    if not members.exists():
        members = Member.visible().filter(is_founding=True)
    return list(members[: conf.home_count])


@register.simple_tag(takes_context=True)
def featured_products(context):
    from products.models import Product, ShopSettings

    conf = ShopSettings.load(request_or_site=context.get("request"))
    if not conf.show_on_home:
        return []
    products = Product.visible().filter(is_featured=True)
    if not products.exists():
        products = Product.visible()
    return list(products[: conf.home_count])


@register.simple_tag
def members_index():
    from members.models import MemberIndexPage

    return MemberIndexPage.for_active_locale()


@register.simple_tag
def shop_index():
    from products.models import ProductIndexPage

    return ProductIndexPage.for_active_locale()


@register.simple_tag
def item_url(obj):
    return obj.get_url() if obj is not None else ""
