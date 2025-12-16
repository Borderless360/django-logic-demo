import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user():
    """Create a regular test user."""
    return User.objects.create_user(
        username='test_user',
        password='testpass123',
        is_staff=False,
        is_superuser=False
    )

@pytest.fixture
def staff_user():
    """Create a staff test user."""
    return User.objects.create_user(
        username='test_staff_user',
        password='testpass123',
        is_staff=True,
        is_superuser=False
    )

@pytest.fixture
def superuser():
    """Create a superuser test user."""
    return User.objects.create_superuser(
        username='test_superuser',
        password='testpass123',
        is_staff=True,
        is_superuser=True
    )
