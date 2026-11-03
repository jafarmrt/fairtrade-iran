import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateStorage(FileSystemStorage):
    """
    Files under PRIVATE_MEDIA_ROOT/<subdir>. The web server never exposes this
    folder; each kind of file has its own permission-checked download view.
    The location is read from settings on every use, so tests can override it.
    """

    def __init__(self, subdir, base_url=None):
        self.subdir = subdir
        super().__init__(base_url=base_url)

    @property
    def base_location(self):
        return os.path.join(settings.PRIVATE_MEDIA_ROOT, self.subdir)

    @property
    def location(self):
        return os.path.abspath(self.base_location)


def private_document_storage():
    """
    Archive documents. Every download goes through Wagtail's document view,
    so collection view restrictions (members, board, commission) always apply.
    """
    return PrivateStorage("documents")
