
def is_staff(instance, user):
    return user.is_staff


def is_user(instance, user):
    return not user.is_staff

def disable():
    return False
