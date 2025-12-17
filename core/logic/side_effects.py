import time
from celery import shared_task


def short_action(*args, **kwargs):
    pass

def long_action(*args, **kwargs):
    time.sleep(10)

def error_for_superuser(obj, *args, **kwargs):
    if kwargs.get('user').is_superuser:
        raise Exception('Error for superuser')