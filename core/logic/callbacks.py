
# NOTE: candidate to push into Django-Logic repo
def run_action(action_name, process_name='process'):
    """ Callback to run an action on the object's process """
    def callback(obj, *args, **kwargs):
        process = getattr(obj, process_name)
        action_method = getattr(process, action_name)
        action_method(*args, **kwargs)
    return callback