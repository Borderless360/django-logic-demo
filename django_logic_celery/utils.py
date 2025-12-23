import importlib
from django.apps import apps
from django.contrib.auth import get_user_model
from django_logic.transition import Transition
from django_logic.state import State
from django_logic.logger import logger as logging

User = get_user_model()


# TODO: move it to django_logic.utils.
# TODO: add test for this function.
def get_transition_from_process(instance, process_name, action_name, process_class=None, field_name='status'):
    """Helper function to retrieve transition from process by action_name"""
    process = get_process_instance(instance, process_name, process_class, field_name)
    transition = find_transition_in_process(process, action_name)
    if transition is None:
        raise ValueError(f"Transition with action_name '{action_name}' not found in process '{process_name}'")
    return transition


# TODO: move it to django_logic.utils.
# TODO: add test for this function.
def find_transition_in_process(process, action_name):
    """Recursively search for transition by action_name in process and nested processes"""
    # Search in current process transitions
    for transition in process.transitions:
        if transition.action_name == action_name:
            return transition
    
    # Search in nested processes recursively
    for sub_process_class in process.nested_processes:
        sub_process = sub_process_class(state=process.state)
        result = find_transition_in_process(sub_process, action_name)
        if result is not None:
            return result
    
    return None


# TODO: move it to django_logic.utils.
# TODO: add test for this function.
def get_process_instance(instance, process_name, process_class=None, field_name='status'):
    """Helper function to get process instance from model or process_class"""
    # First, try to get process from model attribute (if bound)
    try:
        return getattr(instance, process_name)
    except AttributeError:
        # Process is not bound to the model, try to use process_class
        if process_class:
            try:
                # Try to import and instantiate the process class
                module_path, class_name = process_class.rsplit('.', 1)
                module = importlib.import_module(module_path)
                process_class_obj = getattr(module, class_name)
                return process_class_obj(field_name=field_name, instance=instance)
            except (ImportError, AttributeError, ValueError) as e:
                # If import fails, log error and re-raise
                logging.error(f"Failed to import process_class '{process_class}': {e}. "
                            f"Process is not bound to model and process_class cannot be imported.")
                raise
        else:
            # No process_class provided and process is not bound
            raise AttributeError(f"'{instance.__class__.__name__}' object has no attribute '{process_name}' "
                                f"and no process_class was provided")


# TODO: move it to django_logic.utils.
# TODO: add test for this function.
def get_transition(app_label, model_name, instance_id, action_name, process_name, 
    process_class=None, field_name='status', **kwargs) -> tuple[Transition, State]:
    """ Helper function to get transition from arguments """

    app = apps.get_app_config(app_label)
    model = app.get_model(model_name)
    instance = model.objects.get(id=instance_id)
    process = get_process_instance(instance, process_name, process_class, field_name)
    state = process.state
    # Reuse the same process instance instead of creating a new one
    transition = find_transition_in_process(process, action_name)
    if transition is None:
        raise ValueError(f"Transition with action_name '{action_name}' not found in process '{process_name}'")
    return transition, state


def restore_user_object(kwargs):
    """Restore user object from user_id in kwargs"""
    if user_id := kwargs.get('user_id'):
        kwargs['user'] = User.objects.get(id=user_id)
        del kwargs['user_id']
