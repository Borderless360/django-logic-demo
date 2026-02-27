from django.apps import AppConfig


class AutofixerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "autofixer"
    verbose_name = "Autofixer"
