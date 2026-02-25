from django.contrib import admin

from autofixer.models import AlertConfig


@admin.register(AlertConfig)
class AlertConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'alert_type', 'is_active', 'process_class_filter', 'action_name_filter', 'updated_at')
    list_filter = ('alert_type', 'is_active')
    search_fields = ('name', 'process_class_filter', 'action_name_filter')
