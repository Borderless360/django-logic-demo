from celery import shared_task
from celery.result import AsyncResult
from django_logic.logger import logger as logging, transition_logger
from django_logic_celery.utils import get_transition, restore_user_object


@shared_task(acks_late=True)
def complete_transition(*args, **kwargs):
    """Completes transition """
    restore_user_object(kwargs)
    transition, state = get_transition(**kwargs)
    logging.info(f'{state.instance_key} complete transition task started')
    transition.complete_transition(state, **kwargs)
    logging.info(f'{state.instance_key} complete transition task finished')


@shared_task(acks_late=True)
def fail_transition(task_id, *args, **kwargs):
    """
    Transition failure handler handles exceptions and runs fail_transition method of provided Transition.
    Make sure to catch all exceptions by this failure handler as otherwise
    it leads to the worker crash.
    """
    restore_user_object(kwargs)
    transition, state = get_transition(**kwargs)
    try:
        try:
            # If exception is raised in success callback, it will be passed through args
            error = args[0]
        except IndexError:
            task = AsyncResult(task_id)
            error = task.info
        logging.info(f"{state.instance_key} action '{transition.action_name}' failed with error {error}")
        logging.exception(error)
        transition.fail_transition(state, error, **kwargs)
    except Exception as error:
        logging.info(f'{state.instance_key}'
                     f'failure handler failed with error: {error}')
        logging.exception(error)


@shared_task(acks_late=True)
def run_side_effects_as_task(**kwargs):
    """It runs all side-effects of provided transition under a single task"""
    restore_user_object(kwargs)
    transition, state = get_transition(**kwargs)
    
    # Filter out task-specific kwargs that shouldn't be passed to transition methods
    # These are used for task routing and identification but not for transition logic
    task_specific_keys = {
        'app_label', 'model_name', 'instance_id', 'process_name', 
        'field_name', 'action_name'
    }
    transition_kwargs = {k: v for k, v in kwargs.items() if k not in task_specific_keys}
    
    try:
        for side_effect in transition.side_effects.commands:
            transition_logger.info(
                f'{kwargs.get("tr_id")} SideEffect {side_effect.__name__}',
                extra={
                    'tr_id': kwargs.get("tr_id"), 
                    'activity': 'SideEffect', 
                    'side_effect': side_effect.__name__,
                }
            )
            side_effect(state.instance, **transition_kwargs)
    except Exception as error:
        transition_logger.error(error,
            extra={
                'tr_id': kwargs.get("tr_id"), 
            })
        transition.fail_transition(state, error, **transition_kwargs)
    else:
        transition.complete_transition(state, **transition_kwargs)


@shared_task(acks_late=True)
def run_callbacks_as_task(**kwargs):
    """It runs all callbacks of provided transition under a single task"""
    restore_user_object(kwargs)
    transition, state = get_transition(**kwargs)
    
    # Filter out task-specific kwargs that shouldn't be passed to transition methods
    # These are used for task routing and identification but not for transition logic
    task_specific_keys = {
        'app_label', 'model_name', 'instance_id', 'process_name', 
        'field_name', 'action_name'
    }
    transition_kwargs = {k: v for k, v in kwargs.items() if k not in task_specific_keys}
    
    try:
        exception = kwargs.get('exception')
        commands = transition.callbacks.commands if not exception else transition.failure_callbacks.commands
        for callback in commands:
            callback(state.instance, **transition_kwargs)
    except Exception as error:
        logging.info(f'{state.instance_key}'
                     f'callbacks of \'{transition.action_name}\' failed with error: {error}')
        logging.exception(error)
