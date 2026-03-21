class DjangoLogicException(Exception):
    pass


class TransitionNotAllowed(DjangoLogicException):
    pass


class StateLocked(TransitionNotAllowed):
    pass


class PermissionDenied(TransitionNotAllowed):
    pass


class ConditionNotMet(TransitionNotAllowed):
    pass
