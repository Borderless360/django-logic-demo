import json
import logging

from celery import shared_task
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.db import transaction, OperationalError
from django.db.models import Q, F
from django.utils import timezone

from django.contrib.auth import get_user_model
from django_logic_ext.apps import DjangoLogicExtAppConfig as AppConfig
from django_logic_ext.handler import TransitionMessageHandler
from django_logic_ext.models import TransitionMessage
from django_logic_ext.helpers import QueueTransitionHelper, QueueTransitionPool

from core.redis import redis_client

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(acks_late=True)
def handle_transition_message(transition_message_id: int) -> None:
    """ Gets unprocessed message and handles it """
    with transaction.atomic():
        try:
            transition_message = TransitionMessageHandler.fetch_message(transition_message_id)
        except TransitionMessage.DoesNotExist:
            logger.warning(f'TransitionMessage {transition_message_id} already was handled')
        except OperationalError:
            logger.warning(f'TransitionMessageHandler: failed to fetch and lock '
                           f'TransitionMessage {transition_message_id}')
        else:
            handler = TransitionMessageHandler(transition_message)
            handler.handle_message(logger)


@shared_task(acks_late=True)
def handle_transition_messages_starter() -> None:
    """
    Periodically run task to handle transition messages that not processed yet.
    Stops processing messages that already had max errors_count.
    """
    time_limit_dt = timezone.now() - timedelta(minutes=AppConfig.get_setting('OFFSET_TIME_MINUTES'))

    messages_to_process = TransitionMessage.objects\
        .filter(
            created__lt=time_limit_dt,
            is_completed=False,
            errors_count__lt=AppConfig.get_setting('MAX_ERRORS_COUNT')
        ).order_by('created')
    for transition_message in messages_to_process.iterator():
        handle_transition_message.delay(transition_message.id)


@shared_task(acks_late=True)
def cleanup_completed_transition_messages() -> None:
    """ Periodically run task to cleanup completed transition messages. """
    cleanup_limit_dt = timezone.now() - timedelta(days=AppConfig.get_setting('CLEANUP_DAYS'))
    TransitionMessage.objects.filter(created__lt=cleanup_limit_dt,
                                     is_completed=True).delete()


@shared_task(bind=True, max_retries=settings.QUEUE_TRANSITION_MAX_RETRIES)
def execute_side_effects_for_next_one_in_queue(self, queue_key: str):
    """
    Takes transition from provided queue and runs his side effects.
    In the end calls itself with delay to process next transition in queue.
    """
    from django_logic.constants import LogType
    from history_app.django_logic_logger import DjangoLogicClickhouseLogger
    model_history_logger = DjangoLogicClickhouseLogger()

    qt_helper = QueueTransitionHelper(redis_client, queue_key=queue_key)

    serialized_value = qt_helper.take_value_from_tmp()
    if not serialized_value:
        serialized_value = qt_helper.take_value_from_queue(with_tmp=True)
        if not serialized_value:
            qt_helper.unlock_queue()
            return

    value = json.loads(serialized_value)
    app_label = value['app_label']
    model_name = value['model_name']
    instance_id = value['instance_id']
    process_name = value['process_name']
    action_name = value['action_name']
    kwargs = value['kwargs']

    if 'user_id' in kwargs:
        kwargs['user'] = User.objects.get(id=kwargs['user_id'])
        del kwargs['user_id']

    app = apps.get_app_config(app_label)
    model = app.get_model(model_name)
    instance = model.objects.get(id=instance_id)

    log_data = {
        'instance': instance,
        'process_name': process_name,
        'action_name': action_name,
    }

    process = getattr(instance, process_name)
    state = process.state
    transitions = list(process.get_available_transitions(action_name=action_name))
    if not transitions:
        model_history_logger.info(f'execute_side_effects_for_next_one_in_queue: no available transitions, value: {value}',
                                  log_type=LogType.TRANSITION_DEBUG,
                                  log_data=log_data)
        qt_helper.remove_from_tmp(serialized_value)
        self.retry(countdown=0)
    transition = transitions[0]
    model_history_logger.info(f"{state.instance_key} side effects of '{action_name}' started",
                              log_type=LogType.TRANSITION_DEBUG,
                              log_data=log_data)

    try:
        for side_effect in transition.side_effects.commands:
            side_effect(instance, **kwargs)
    except Exception as error:
        model_history_logger.info(f"{state.instance_key} side effects of '{transition.action_name}' failed with error: {error}",
                                  log_type=LogType.TRANSITION_DEBUG,
                                  log_data=log_data)
        model_history_logger.error(error,
                                   log_type=LogType.TRANSITION_ERROR,
                                   log_data=log_data)

        try:
            transition.fail_transition(state, error, **kwargs)
        except Exception as e:
            model_history_logger.info(f'execute_side_effects_for_next_one_in_queue fail_transition failed: {str(e)}',
                                      log_type=LogType.TRANSITION_DEBUG,
                                      log_data=log_data)
            qt_helper.remove_from_tmp(serialized_value)
            self.retry(countdown=0)
    else:
        model_history_logger.info(f"{state.instance_key} side effects of '{transition.action_name}' succeeded",
                                  log_type=LogType.TRANSITION_DEBUG,
                                  log_data=log_data)

        try:
            transition.complete_transition(state, **kwargs)
        except Exception as e:
            model_history_logger.info(f'execute_side_effects_for_next_one_in_queue complete_transition failed: {str(e)}',
                                      log_type=LogType.TRANSITION_DEBUG,
                                      log_data=log_data)
            qt_helper.remove_from_tmp(serialized_value)
            self.retry(countdown=0)

    qt_helper.remove_from_tmp(serialized_value)
    execute_side_effects_for_next_one_in_queue.delay(queue_key=queue_key)


@shared_task
def check_stuck_queue_transition():
    """ Periodically checks if some queues are stuck and launches them again. """
    pool = QueueTransitionPool(redis_client)

    timestamp_limit = pool.get_timestamp_limit()
    current_queues = pool.get_queues()
    for queue_key in current_queues:
        queue_key = queue_key.decode('utf-8')
        qt_helper = QueueTransitionHelper(redis_client, queue_key=queue_key)

        serialized_first_value = qt_helper.get_first_value()
        if not serialized_first_value:
            qt_helper.unlock_queue()
            pool.remove_queue(queue_key)
            continue

        first_value = json.loads(serialized_first_value)
        if first_value['timestamp'] > timestamp_limit:
            continue

        logger.info(f'check_stuck_queue_transition: stuck queue - {queue_key}')
        execute_side_effects_for_next_one_in_queue.delay(queue_key=queue_key)


@shared_task
def check_stuck_fulfilling_orders():
    """
    Checks orders that stuck in fulfilling state and fulfils them again.
    Stuck order has no labels_generated_date for a long time or labels_generated_date that earlier than
    fulfilling_started_date in case of refulfilling.
    """
    from order.models import Order
    from order.business_logic.actions import refulfil_stuck_order

    time_limit_dt = timezone.now() - timezone.timedelta(minutes=settings.FULFILLING_TIME_LIMIT_MINUTES)
    orders = Order.objects \
        .filter(state=Order.STATE_CHOICES.fulfilling, fulfilment__fulfilling_started_date__isnull=False,
                fulfilment__fulfilling_started_date__lt=time_limit_dt) \
        .filter(Q(fulfilment__labels_generated_date__isnull=True) |
                Q(fulfilment__labels_generated_date__lt=F('fulfilment__fulfilling_started_date')))
    for order in orders.select_related('fulfilment').iterator():
        refulfil_stuck_order(order)
