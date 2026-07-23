import requests
import os

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order
from .serializers import OrderSerializer

from django.core.mail import send_mail
from django.conf import settings

from decouple import config

# Create your views here.

class OrderCreateView(APIView):
    def post(self, request):
        serializer = OrderSerializer(data=request.data)
        if serializer.is_valid():
            order = serializer.save()
            print(request.data)

            try:
                response = requests.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {config('RESEND_API_KEY')}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": "onboarding@resend.dev",
                        "to": ["orders.arenaventures@gmail.com"],
                        "subject": f"New Order from {order.full_name}",
                        "html": f"""
                            <h2>New Order Received</h2>

                            <p><strong>Name:</strong> {order.full_name}</p>
                            <p><strong>Phone:</strong> {order.phone_number}</p>
                            <p><strong>Email:</strong> {order.email or "Not provided"}</p>
                            <p><strong>Product:</strong> {order.product}</p>
                            <p><strong>Quantity:</strong> {order.quantity}</p>
                            <p><strong>Address:</strong> {order.address}</p>
                            <p><strong>Note:</strong> {order.note or "Not provided"}</p>
                        """,
                    },
                    timeout=30,
                )
            except Exception as e:
                print(e)

            return Response(
                {
                    "success": True,
                    "message": "Order submitted successfully.",
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
