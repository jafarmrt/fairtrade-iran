from archive.storage import PrivateStorage


def appeal_storage():
    """Appeal attachments, downloadable only through appeals.views.attachment."""
    return PrivateStorage("appeals")
