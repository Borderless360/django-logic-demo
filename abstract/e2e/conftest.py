import os
import pytest
from abstract.e2e.utils import verify_celery_worker_running

pytest_plugins = ["celery.contrib.pytest", "core.fixtures", ]

@pytest.fixture(scope='session')
def celery_config():
    # Use the same Redis broker as the worker in compose.yml
    # This ensures tests use the existing worker instead of spawning a new one
    broker_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379')
    return {
        'broker_url': broker_url,
        'result_backend': broker_url,  # Use Redis as result backend too
    }

@pytest.fixture(scope='session')
def celery_app(celery_config):
    """Use the Django Celery app for testing.
    Configured to use the existing worker from compose.yml."""
    from demo.celery_app import app
    # Apply the broker configuration to ensure it uses Redis
    app.conf.update(
        broker_url=celery_config['broker_url'],
        result_backend=celery_config['result_backend'],
    )
    # Ensure the app is set as the current app so CeleryTransition uses it
    # import celery
    # celery.current_app = app
    # Register ping task for worker health checks
    from celery.contrib.testing.tasks import ping
    if 'celery.ping' not in app.tasks:
        app.tasks.register(ping)
    return app

@pytest.fixture(scope='session', autouse=True)
def verify_worker_before_tests(celery_app):
    """Verify that the Celery worker from compose.yml is running before all tests."""
    assert verify_celery_worker_running(celery_app), "Celery worker from compose.yml is not running"
