from archive.storage import PrivateStorage


def receipt_storage():
    """Buyers' payment receipts: PRIVATE_MEDIA_ROOT/orders/, served only by staff- or seller-checked views."""
    return PrivateStorage("orders")
