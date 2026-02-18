from django_logic.transition import Transition
from django_logic.state import State
from .tasks import run_transition_in_background

class CeleryTransition(Transition):
    """
    Transition that should be run in background if not yet in background.
    Default implementation is to use Celery task.
    """
    def __init__(self, action_name: str, sources: list, target: str, queue_name: str = 'celery', **kwargs):
        self.queue_name = queue_name
        super().__init__(action_name=action_name, sources=sources, target=target, **kwargs)

    def change_state(self, state: State, **kwargs):
        """
        Change the state to the in-progress state.
        """
        kwargs.pop('background_mode', None)  # avoid duplicate kwarg when caller passes it
        return super().change_state(state, background_mode=True, **kwargs)

    def run_in_background(self, state: State, **kwargs):
        """
        Run the transition in background.
        """
        task_kwargs = self.get_task_kwargs(state, **kwargs)
        run_transition_in_background.apply_async(kwargs=task_kwargs, queue=self.queue_name)
