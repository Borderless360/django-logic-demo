import time


def short_action(*args, **kwargs):
    pass


def long_action(*args, **kwargs):
    time.sleep(10)


def error_for_superuser(obj, *args, **kwargs):
    if not kwargs.get('user'):
        raise Exception('User is required')
    if kwargs.get('user').is_superuser:
        raise Exception('Error for superuser')
    