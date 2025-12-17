import pytest
from core.utils import get_or_create_user, get_or_create_staff_user, get_or_create_superuser


@pytest.fixture
def user():
    """Create a regular test user."""
    return get_or_create_user()

@pytest.fixture
def staff_user():
    """Create a staff test user."""
    return get_or_create_staff_user()

@pytest.fixture
def superuser():
    """Create a superuser test user."""
    return get_or_create_superuser()
