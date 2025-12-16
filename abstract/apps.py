from django_logic import ProcessManager
from django.apps import AppConfig


class AbstractConfig(AppConfig):
    name = 'abstract'

    def ready(self):
        # Initialize the process after the app is ready
        # from .logic.process import AProcess, BProcess, CProcess
        # from .models import A, B, C
        # ProcessManager.bind_model_process(A, AProcess, 'status')
        # ProcessManager.bind_model_process(B, BProcess, 'status')
        # ProcessManager.bind_model_process(C, CProcess, 'status')
        pass
