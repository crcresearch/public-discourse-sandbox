from django.apps import AppConfig


class PdsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'public_discourse_sandbox.pds_app'
    
    def ready(self):
        """
        Import signals when the app is ready.
        This ensures that signal handlers are registered.
        """
        import public_discourse_sandbox.pds_app.signals  # noqa: F401
