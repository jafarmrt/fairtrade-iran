"""The cart lives in the session: {product id: quantity}."""

from products.models import Product, ShopSettings

from .models import Seller

SESSION_KEY = "shop_cart"
SHIPPING_KEY = "shop_shipping"  # {member id: chosen ShippingOption id}
MAX_QUANTITY = 99


class Line:
    def __init__(self, product, quantity):
        self.product = product
        self.requested = quantity
        available = product.available_quantity
        self.quantity = quantity if available is None else min(quantity, available)
        self.unit_price = product.price or 0

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def reduced(self):
        return self.quantity < self.requested


class Group:
    """The lines of one producer, which become one order."""

    def __init__(self, member, seller, shop, chosen=None):
        self.member, self.seller, self.lines = member, seller, []
        self.shop = shop
        self.options = seller.active_shipping_options()
        self.option = next((o for o in self.options if o.pk == chosen), self.options[0] if self.options else None)

    @property
    def subtotal(self):
        return sum(line.line_total for line in self.lines)

    @property
    def shipping(self):
        return self.seller.shipping_for(self.subtotal, self.option)

    @property
    def free_shipping(self):
        return bool(self.seller.free_shipping_over and self.subtotal >= self.seller.free_shipping_over)

    def option_price(self, option):
        return 0 if self.free_shipping else option.fee

    @property
    def total(self):
        return self.subtotal + self.shipping

    @property
    def is_house(self):
        return self.seller.mode == Seller.Mode.HOUSE


class Cart:
    def __init__(self, request):
        self.session = request.session
        raw = self.session.get(SESSION_KEY) or {}
        self.data = {str(k): int(v) for k, v in raw.items() if str(k).isdigit() and int(v) > 0}

    @property
    def shipping_choices(self):
        raw = self.session.get(SHIPPING_KEY) or {}
        return {int(k): int(v) for k, v in raw.items() if str(k).isdigit() and str(v).isdigit()}

    def choose_shipping(self, member_id, option_id):
        choices = {str(k): v for k, v in self.shipping_choices.items()}
        choices[str(member_id)] = int(option_id)
        self.session[SHIPPING_KEY] = choices
        self.session.modified = True

    def save(self):
        self.session[SESSION_KEY] = self.data
        self.session.modified = True

    def add(self, product_id, quantity=1):
        key = str(product_id)
        self.data[key] = min(self.data.get(key, 0) + max(quantity, 1), MAX_QUANTITY)
        self.save()

    def set(self, product_id, quantity):
        key = str(product_id)
        if quantity <= 0:
            self.data.pop(key, None)
        else:
            self.data[key] = min(quantity, MAX_QUANTITY)
        self.save()

    def clear(self):
        self.data = {}
        self.save()

    @property
    def count(self):
        return sum(self.data.values())

    def __bool__(self):
        return bool(self.data)

    def groups(self, products=None):
        """Lines grouped by producer. Products that can no longer be bought are dropped from the cart."""
        shop = ShopSettings.load()
        if products is None:
            products = Product.visible().filter(pk__in=[int(k) for k in self.data])
        by_id = {p.pk: p for p in products}
        groups, dropped = {}, []
        for key, quantity in list(self.data.items()):
            product = by_id.get(int(key))
            if product is None or not product.can_add_to_cart(shop):
                dropped.append(key)
                continue
            group = groups.get(product.member_id)
            if group is None:
                group = groups[product.member_id] = Group(product.member, Seller.for_member(product.member), shop,
                                                          self.shipping_choices.get(product.member_id))
            group.lines.append(Line(product, quantity))
        if dropped:
            for key in dropped:
                self.data.pop(key, None)
            self.save()
        return list(groups.values())
