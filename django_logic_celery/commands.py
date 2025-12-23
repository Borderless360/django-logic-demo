from celery import signature, group, chain
from django.db import transaction
from django_logic.logger import logger as logging
from django_logic.commands import SideEffects, Callbacks
from django_logic.state import State
from django_logic_celery.tasks import run_side_effects_as_task, run_callbacks_as_task, complete_transition, fail_transition


class CeleryCommandMixin:
    """Celery command mixin"""

    def execute(self, state: State, **kwargs):
        if not self.commands:
            return super().execute(state)

        task_kwargs = self.get_task_kwargs(state, **kwargs)
        self.queue_task(task_kwargs)
        logging.info(f'{self.__class__.__name__} has been added to queue with '
                     f'the following parameters {task_kwargs}')

    def get_task_kwargs(self, state: State, **kwargs):
        task_kwargs = dict(
            app_label=state.instance._meta.app_label,
            model_name=state.instance._meta.model_name,
            instance_id=state.instance.pk,
            process_name=state.process_name,
            field_name=state.field_name,
            action_name=self._transition.action_name,
            tr_id=kwargs.get("tr_id"), 
        )
        
        # Only include serializable kwargs - convert objects to IDs where possible
        serializable_kwargs = {}
        for key, value in kwargs.items():
            if key == 'exception':
                serializable_kwargs[key] = value
                continue
            # Skip functions and other callables
            if callable(value) and not isinstance(value, type):
                continue
            # Convert user objects to user_id
            if key == 'user' and hasattr(value, 'pk'):
                serializable_kwargs['user_id'] = value.pk
                continue
            # Include only primitive serializable types
            if isinstance(value, (str, int, float, bool, type(None))):
                serializable_kwargs[key] = value
        
        task_kwargs.update(serializable_kwargs)

        return task_kwargs

    def queue_task(self, task_kwargs):
        return NotImplementedError


class SideEffectTasks(CeleryCommandMixin, SideEffects):
    """
    Celery side-effects creates a chain of celery tasks where every task is a command.
    In case of success it triggers complete_transition task
    In case of failure it triggers fail_transition task
    """

    def queue_task(self, task_kwargs):
        # Convert function objects to task names (strings)
        task_names = []
        for cmd in self.commands:
            if isinstance(cmd, str):
                task_names.append(cmd)
            elif hasattr(cmd, 'name'):
                # Celery task object
                task_names.append(cmd.name)
            elif callable(cmd):
                # Regular function - use its name (assumes it's registered as a Celery task)
                task_names.append(cmd.__name__)
            else:
                task_names.append(str(cmd))
        
        header = [signature(task_name, kwargs=task_kwargs) for task_name in task_names]
        header = chain(*header)
        body = complete_transition.s(**task_kwargs)
        tasks = chain(header | body).on_error(fail_transition.s(**task_kwargs))
        transaction.on_commit(tasks.delay)


class CallbacksTasks(CeleryCommandMixin, Callbacks):
    """Callbacks commands executed as a celery group of tasks"""

    def queue_task(self, task_kwargs):
        tasks = [signature(task_name, kwargs=task_kwargs) for task_name in self.commands]
        transaction.on_commit(group(tasks))


class SideEffectSingleTask(CeleryCommandMixin, SideEffects):
    """Side-effects commands executed as a single celery task"""

    def queue_task(self, task_kwargs):
        sig = run_side_effects_as_task.signature(kwargs=task_kwargs)
        transaction.on_commit(sig.delay)


class CallbacksSingleTask(CeleryCommandMixin, Callbacks):
    """Callbacks commands executed as a single celery task"""

    def queue_task(self, task_kwargs):
        sig = run_callbacks_as_task.signature(kwargs=task_kwargs)
        transaction.on_commit(sig.delay)
