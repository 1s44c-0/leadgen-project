from rest_framework import serializers
from .models import Order

class OrderSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    
    class Meta:
        model = Order
        fields = '__all__'