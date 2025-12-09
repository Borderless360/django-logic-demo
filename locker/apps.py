from django_logic import ProcessManager
from django.apps import AppConfig


class LockerConfig(AppConfig):
    name = 'locker'

    def ready(self):
        # Initialize the process after the app is ready
        from .logic.process import LockerProcess
        from .models import Lock
        ProcessManager.bind_model_process(Lock, LockerProcess, 'status')
