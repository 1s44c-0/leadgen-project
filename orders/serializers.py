from rest_framework import serializers
from .models import Order


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "id",
            "full_name",
            "phone_number",
            "email",
            "product",
            "quantity",
            "address",
            "note",
            "amount",
            "payment_method",
            "payment_status",
            "tx_ref",
            "paid_at",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "amount",
            "payment_status",
            "tx_ref",
            "paid_at",
            "created_at",
        ]