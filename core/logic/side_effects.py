import time
from celery import shared_task


def short_action(*args, **kwargs):
    pass

@shared_task(acks_late=True)
def long_action(*args, **kwargs):
    time.sleep(10)


def do_something_a(*args, **kwargs):
    time.sleep(1)
def do_something_b(*args, **kwargs):
    time.sleep(1)
def do_something_c(*args, **kwargs):
    time.sleep(1)
