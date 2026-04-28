# core/apps.py

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Importing signals here causes all @receiver decorators to register
        # when Django starts. Without this, signals are never connected.
        import core.signals  # noqa: F401