from importlib import import_module
from django_logic.state import State


__all__ = (
    'extract_command_for_state',
)


def extract_command_for_state(command: str, state: State, **kwargs) -> tuple[callable, dict]:
    """
    Extracts function from command and returns it with kwargs.
    Kwargs are filled with instance metadata.
    """
    module_name, function_name = command.rsplit('.', 1)
    module = import_module(module_name)
    function = getattr(module, function_name)
    function_kwargs = {
        **kwargs,
        'app_label': state.instance._meta.app_label,
        'model_name': state.instance._meta.model_name,
        'instance_id': state.instance.pk,
        'process_name': state.process_name,
        'field_name': state.field_name
    }
    return function, function_kwargs
