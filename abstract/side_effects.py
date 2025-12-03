import time
from .models import A

# NOTE: Side effects also can be used as callbacks

def short_action(*args, **kwargs):
    pass

def long_action(*args, **kwargs):
    time.sleep(10)
    pass

def fail(obj, *args, **kwargs):
    if obj.raise_error:
        raise Exception('Crash')

def fail_always(obj, *args, **kwargs):
    raise Exception('Crash')

def run_process_A(*args, **kwargs):
    pass

def run_process_B(obj_a: A,*args, **kwargs):
    obj_a.b.process.B0_B1()
    obj_a.b.process.B1_B2()

def run_process_C(*args, **kwargs):
    pass

def save_error_code(obj, *args, **kwargs):
    obj.error_code = 1 
    obj.save(update_fields=['error_code'])


