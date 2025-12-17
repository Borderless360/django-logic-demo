from django.apps import AppConfig
from django.conf import settings


class DjangoLogicExtAppConfig(AppConfig):
    """ django-logic library extension """
    name = 'django_logic_ext'
    settings_prefix = 'DJANGO_LOGIC_EXT_'

    @classmethod
    def get_setting(cls, name: str, default_value=None):
        return getattr(settings, cls.settings_prefix + name, default_value)

    def ready(self) -> None:
        """ Register signals """
        from django_logic_ext import signals
