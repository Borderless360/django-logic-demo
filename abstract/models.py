from django.db import models
from model_utils import Choices

A_STATES = Choices(
    ('A0', 'A0'),
    ('A1', 'A1'),
    ('A2', 'A2'),
    ('A3', 'A3'),
    ('A4', 'A4'),
    ('A5', 'A5'),
)
B_STATES = Choices(
    ('B0', 'B0'),
    ('B1', 'B1'),
    ('B2', 'B2'),
    ('Err', 'Err'),
)
C_STATES = Choices(
    ('C0', 'C0'),
    ('C1', 'C1'),
    ('C2', 'C2'),
    ('C3', 'C3'),
)

class C(models.Model):
    name = models.CharField(max_length=100)
    raise_error = models.BooleanField(default=False, help_text='If True, the process will raise an error')
    error_code = models.IntegerField(default=0, help_text='Catched error code')
    status = models.CharField(max_length=3, choices=C_STATES, default=C_STATES.C0)

class B(models.Model):
    name = models.CharField(max_length=100)
    raise_error = models.BooleanField(default=False, help_text='If True, the process will raise an error')
    error_code = models.IntegerField(default=0, help_text='Catched error code')
    c = models.ForeignKey(C, on_delete=models.CASCADE)
    status = models.CharField(max_length=3, choices=B_STATES, default=B_STATES.B0)

class A(models.Model):
    name = models.CharField(max_length=100)
    raise_error = models.BooleanField(default=False, help_text='If True, the process will raise an error')
    error_code = models.IntegerField(default=0, help_text='Catched error code')
    b = models.ForeignKey(B, on_delete=models.CASCADE)
    status = models.CharField(max_length=3, choices=A_STATES, default=A_STATES.A0)
