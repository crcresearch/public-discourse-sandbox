from django.apps import AppConfig


class PdsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "public_discourse_sandbox.pds_app"

    def ready(self):
        """
        Import signals when the app is ready.
        This ensures that signal handlers are registered.
        """
        try:
            import public_discourse_sandbox.pds_app.signals  # noqa: F401
            import public_discourse_sandbox.pds_app.tasks  # noqa: F401
        except ImportError:
            pass
