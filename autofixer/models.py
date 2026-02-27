from django.db import models


class AutofixerMarker(models.Model):
    class Meta:
        managed = False
        verbose_name = "Autofixer marker"
        verbose_name_plural = "Autofixer markers"

