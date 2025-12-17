import pytest
from django.db import connections

pytest_plugins = ["celery.contrib.pytest", "core.fixtures", ]

@pytest.fixture(scope='session')
def celery_config():
    # Use an in-memory broker like 'memory://' for testing speed
    return {
        'broker_url': 'memory://',
        'result_backend': 'cache+memory://',
    }

@pytest.fixture(scope='session')
def celery_app():
    """Use the Django Celery app for testing."""
    from demo.celery_app import app
    # Register ping task for worker health checks
    from celery.contrib.testing.tasks import ping
    if 'celery.ping' not in app.tasks:
        app.tasks.register(ping)
    return app

@pytest.fixture
def celery_worker_parameters():
    """Disable ping check to avoid issues."""
    return {
        'perform_ping_check': False,
    }

@pytest.fixture(autouse=True)
def close_db_connections():
    """Close database connections before each test to avoid issues with celery_worker."""
    yield
    # Close all database connections after test
    connections.close_all()
