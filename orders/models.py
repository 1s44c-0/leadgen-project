from django.db import models

from django.core.mail import send_mail
from django.conf import settings

# Create your models here.

class Order(models.Model):
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    product = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)
    address = models.TextField()
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.product} ({self.quantity})"
