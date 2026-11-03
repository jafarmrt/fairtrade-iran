from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Lets people sign in with their e-mail address as well as their username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or "@" not in username or password is None:
            return None
        users = list(get_user_model().objects.filter(email__iexact=username.strip())[:2])
        if len(users) != 1:
            return None
        user = users[0]
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
