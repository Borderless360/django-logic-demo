import celery
import environ
from celery.app import trace
from django.conf import settings

env = environ.Env()
trace.LOG_RECEIVED = """\
Task %(name)s[%(id)s] received %(args)s %(kwargs)s\
"""

app = celery.Celery('demo')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self, *args, **kwargs):
    print('Request: {0!r}'.format(self.request))
    from time import sleep
    sleep(2)
