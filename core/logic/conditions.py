
def is_staff(instance, user):
    if not user:
        return False
    return user.is_staff


def is_user(instance, user):
    print(f"is_user: {user}, {user.is_staff} {instance}")
    if not user:
        return False
    return not user.is_staff

def disable():
    return False
