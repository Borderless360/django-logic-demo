from django.db import models

from model_utils.models import TimeStampedModel


class TransitionMessage(TimeStampedModel):
    is_completed = models.BooleanField(default=False)

    errors_count = models.PositiveIntegerField(default=0)
    last_error_dt = models.DateTimeField(blank=True, null=True)
    last_error_message = models.TextField(blank=True)

    app_label = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    instance_id = models.PositiveIntegerField()
    process_name = models.CharField(max_length=100)
    transition_name = models.CharField(max_length=100)
    args = models.JSONField(blank=True, default=list)
    kwargs = models.JSONField(blank=True, default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['app_label', 'model_name', 'instance_id'],
                                    condition=models.Q(is_completed=False),
                                    name='only_one_uncompleted_transition_per_instance')
        ]
        indexes = [
            models.Index(fields=['created', 'is_completed']),
        ]

    def __str__(self):
        return f'{self.app_label}.{self.model_name}(id={self.instance_id}).{self.process_name}.{self.transition_name}'

    def mark_as_completed(self):
        self.is_completed = True
        self.save(update_fields=['is_completed'])

