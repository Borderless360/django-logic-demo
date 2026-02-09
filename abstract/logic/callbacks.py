
def save_error(obj, *args, **kwargs):
    """ Failure callback to save error to the object """
    exception = kwargs.get('exception')
    if exception:
        obj.error = str(exception)
    else:
        obj.error = None
    obj.save(update_fields=['error'])



