from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order
from .serializers import OrderSerializer

from django.core.mail import send_mail
from django.conf import settings

# Create your views here.

class OrderCreateView(APIView):
    def post(self, request):
        serializer = OrderSerializer(data=request.data)
        if serializer.is_valid():
            order = serializer.save()

            send_mail(
                subject=f'New Order from {order.full_name}',
                message=(
                    f'Hello, a new order has been placed by {order.full_name}. Please check the admin panel for details.\n\n'
                    f'Order Details:\n'
                    f'Product: {order.product}\n'
                    f'Quantity: {order.quantity}\n'
                    f'Address: {order.address}\n'
                    f'Note: {order.note}'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['olorunfemiisaac084@gmail.com'],
                fail_silently=False,
            ),

            return Response(
                {
                    "success": True,
                    "message": "Order submitted successfully.",
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
