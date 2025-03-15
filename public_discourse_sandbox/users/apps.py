import contextlib

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    name = "public_discourse_sandbox.users"
    verbose_name = _("Users")

    def ready(self):
        with contextlib.suppress(ImportError):
            import public_discourse_sandbox.users.signals  # noqa: F401
