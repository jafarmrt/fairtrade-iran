import os

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from .models import Complaint


@login_required
def complaint_file(request, pk):
    """Download a complaint attachment; only for users who can see complaints (the commission)."""
    if not request.user.has_perm("contact.view_complaint"):
        raise PermissionDenied
    complaint = get_object_or_404(Complaint, pk=pk)
    if not complaint.attachment:
        raise Http404
    ext = os.path.splitext(complaint.attachment.name)[1]
    try:
        handle = complaint.attachment.open("rb")
    except FileNotFoundError:
        raise Http404
    response = FileResponse(handle, as_attachment=True,
                            filename=f"complaint-{complaint.tracking_code}{ext}")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
