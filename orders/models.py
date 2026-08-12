from django.db import models


class Order(models.Model):

    PAYMENT_METHOD_CHOICES = [
        ("online", "Pay Online"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("unpaid", "Not Paid"),
        ("pending", "Payment Pending"),
        ("paid", "Paid"),
        ("failed", "Payment Failed"),
        ("cancelled", "Payment Cancelled"),
    ]

    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)

    product = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)
    address = models.TextField()
    note = models.TextField(blank=True, null=True)

    # Payment information
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=1000.00
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="online"
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="unpaid"
    )

    paystack_reference = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True
    )

    paid_at = models.DateTimeField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.product} ({self.quantity})"