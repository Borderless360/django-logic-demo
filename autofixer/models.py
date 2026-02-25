from django.db import models


class AlertConfig(models.Model):
    """Configurable alert rule.

    Each row describes *one* alert channel (email or webhook) with its own
    threshold settings and optional filters.  Multiple rows may be active
    simultaneously so that the same anomaly can be delivered to several
    destinations.
    """

    ALERT_TYPES = [
        ('email', 'Email'),
        ('webhook', 'Webhook'),
    ]

    name = models.CharField(max_length=255)
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    is_active = models.BooleanField(default=True)

    # Email-specific
    email_recipients = models.TextField(
        blank=True,
        help_text='Comma-separated email addresses',
    )
    email_from = models.EmailField(blank=True)

    # Webhook-specific
    webhook_url = models.URLField(blank=True)
    webhook_headers = models.JSONField(default=dict, blank=True)

    # Threshold overrides (None = use global defaults from settings)
    std_dev_multiplier = models.FloatField(
        null=True, blank=True,
        help_text='Override: alert if duration > mean + multiplier * std_dev',
    )
    min_samples = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Override: minimum samples before detection activates',
    )

    # Optional scope filters
    process_class_filter = models.CharField(
        max_length=255, blank=True,
        help_text='Only alert for this process class (empty = all)',
    )
    action_name_filter = models.CharField(
        max_length=255, blank=True,
        help_text='Only alert for this action name (empty = all)',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Alert Configuration'
        verbose_name_plural = 'Alert Configurations'

    def __str__(self):
        return f'{self.name} ({self.alert_type})'

    def matches(self, process_class: str, action_name: str) -> bool:
        if self.process_class_filter and self.process_class_filter != process_class:
            return False
        if self.action_name_filter and self.action_name_filter != action_name:
            return False
        return True
