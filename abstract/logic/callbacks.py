
def save_error(obj, *args, **kwargs):
    """ Failure callback to save error to the object """
    obj.error = kwargs.get('exception')
    obj.save(update_fields=['error'])


