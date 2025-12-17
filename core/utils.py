from django.contrib.auth import get_user_model


User = get_user_model()
def get_or_create_user():
    """Create a regular test user."""
    try:
        user = User.objects.get(username='test_user')
    except User.DoesNotExist:
        user = User.objects.create_user(
            username='test_user',
            password='testpass123',
            is_staff=False,
            is_superuser=False
        )
    return user

def get_or_create_staff_user():
    """Create a staff test user."""
    try:
        user = User.objects.get(username='test_staff_user')
    except User.DoesNotExist:
        user = User.objects.create_user(
            username='test_staff_user',
            password='testpass123',
            is_staff=True,
            is_superuser=False
        )
    return user

def get_or_create_superuser():
    """Create a superuser test user."""
    try:
        user = User.objects.get(username='test_superuser')
    except User.DoesNotExist:
        user = User.objects.create_superuser(
            username='test_superuser',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
    return user
