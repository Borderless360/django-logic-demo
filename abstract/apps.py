from django_logic import ProcessManager
from django.apps import AppConfig


class AbstractConfig(AppConfig):
    name = 'abstract'

    def ready(self):
        # Initialize the process after the app is ready
        from .logic.test_basic import BasicProcess
        from .logic.test_branch import BranchProcess
        from .logic.test_chain import ChainProcess
        from .logic.test_nested_calls import AProcess, BProcess, CProcess
        # from .models import A, B, C
        # ProcessManager.bind_model_process(A, AProcess, 'status')
        # ProcessManager.bind_model_process(B, BProcess, 'status')
        # ProcessManager.bind_model_process(C, CProcess, 'status')

