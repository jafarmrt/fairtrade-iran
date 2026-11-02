from archive.storage import PrivateStorage


def complaint_storage():
    """Complaint attachments, downloadable only through contact.views.complaint_file."""
    return PrivateStorage("complaints")
