import logging
from django.urls import path
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.utils.encoding import force_str
from django_logic.exceptions import TransitionNotAllowed

logger = logging.getLogger(__name__)

class DjangoLogicAdminMixin:
    """Mixin to add django-logic transition buttons to admin change form"""

    change_form_template = 'admin/django_logic_change_form.html'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/transition/<str:transition_name>/',
                self.admin_site.admin_view(self.transition_view),
                name=f'{self.model._meta.model_name}_transition',
            ),
        ]
        return custom_urls + urls

    def get_redirect_url(self, request, obj):
        """
        Hook to adjust the redirect post-save.
        """
        return request.path

    def transition_view(self, request, object_id, transition_name):
        obj = self.get_object(request, object_id)
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, self.model._meta, object_id)
        
        try:
            with transaction.atomic():
                # Get the process instance and call the transition
                process = getattr(obj, 'process', None)
                if process and hasattr(process, transition_name):
                    transition = getattr(process, transition_name)
                    transition()
                    msg = '%(obj)s successfully transitioned to %(transition)s' % {
                        'obj': force_str(obj),
                        'transition': transition_name
                    }
                    self.message_user(request, msg, messages.SUCCESS)
        except TransitionNotAllowed as e:
            self.message_user(request, str(e), messages.ERROR)

        redirect_url = self.get_redirect_url(request=request, obj=obj)
        return HttpResponseRedirect(redirect_url)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)

        # Handle transition POST
        if request.method == "POST" and "do_transition" in request.POST:
            transition_name = request.POST["do_transition"]
            try:
                process = getattr(obj, 'process', None)
                if process and hasattr(process, transition_name):
                    getattr(process, transition_name)()
                    self.message_user(request, f"Transition '{transition_name}' executed successfully.", messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"Error: {e}", messages.ERROR)
            return HttpResponseRedirect(request.path)

        # Usual context for rendering buttons
        if obj and hasattr(obj, 'process'):
            process = obj.process
            available_transitions = []
            for transition in process.get_available_transitions():
                available_transitions.append({'name': transition.action_name})
            extra_context['available_transitions'] = available_transitions

        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        """
        Override save_model to ensure we're not interfering with transitions
        """
        super().save_model(request, obj, form, change) 