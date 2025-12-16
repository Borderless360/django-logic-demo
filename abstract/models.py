from django.db import models
from model_utils import Choices


STATES = Choices(
    ('A', 'A'),
    ('B', 'B'),
    ('C', 'C'),
    ('D', 'D'),
    ('E', 'E'),
    ('F', 'F'),
    ('Err', 'Err'),
)

class BaseModel(models.Model):
    name = models.CharField(max_length=100)
    error = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=3, choices=STATES, default=STATES.A)

    class Meta:
        abstract = True

class C(BaseModel):
    pass

class B(BaseModel):
    c = models.ForeignKey(C, on_delete=models.CASCADE, null=True, blank=True)

class A(BaseModel):
    b = models.ForeignKey(B, on_delete=models.CASCADE, null=True, blank=True)
