from django.contrib import admin

from django_logic_ext.models import TransitionMessage


class TransitionMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'created', 'modified', 'app_label', 'model_name', 'instance_id', 'process_name',
                    'transition_name', 'is_completed', 'errors_count', 'last_error_dt', 'last_error_message']
    list_filter = ['is_completed', 'model_name']
    search_fields = ['instance_id', 'process_name', 'transition_name', 'last_error_message']


admin.site.register(TransitionMessage, TransitionMessageAdmin)
