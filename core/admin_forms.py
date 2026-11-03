"""Forms used by the Wagtail admin (set in settings: WAGTAILADMIN_USER_LOGIN_FORM)."""

from django.utils.translation import gettext_lazy
from wagtail.admin.forms.auth import LoginForm


class AdminLoginForm(LoginForm):
    """
    Wagtail's sign-in form gives the password field no label, so Django falls back to the
    untranslated field name and the Persian page showed "Password". Give it a translated one.
    """

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["password"].label = gettext_lazy("Password")
