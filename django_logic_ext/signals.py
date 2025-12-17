from django.db.models.signals import post_save
from django.dispatch import receiver

from django_logic_ext.models import TransitionMessage
from django_logic_ext.tasks import handle_transition_message
from django.db import transaction


@receiver(post_save, sender=TransitionMessage)
def on_transition_handler_created(sender, instance, created, **kwargs):
    """ Immediately runs handling task when new transition message is created. """
    if created:
        transaction.on_commit(lambda: handle_transition_message.delay(instance.id))
