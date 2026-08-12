import requests
import uuid

from django.shortcuts import redirect
from django.utils import timezone

from decouple import config

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order
from .serializers import OrderSerializer


# ============================================================
# PRODUCT PRICE
# ============================================================

PRODUCT_PRICE = 1000  # ₦1,000 per unit


# ============================================================
# SEND ORDER EMAIL
# ============================================================

def send_order_email(order):
    payment_status = (
        "PAID"
        if order.payment_status == "paid"
        else "NOT PAID"
    )

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
                "subject": f"New Paid Order from {order.full_name}",
                "html": f"""
                    <h2>New Order Received</h2>

                    <p><strong>Name:</strong> {order.full_name}</p>
                    <p><strong>Phone:</strong> {order.phone_number}</p>
                    <p><strong>Email:</strong> {order.email or "Not provided"}</p>

                    <p><strong>Product:</strong> {order.product}</p>
                    <p><strong>Quantity:</strong> {order.quantity}</p>

                    <p><strong>Unit Price:</strong>
                    ₦{PRODUCT_PRICE:,.2f}</p>

                    <p><strong>Total Amount:</strong>
                    ₦{order.amount:,.2f}</p>

                    <p><strong>Payment Status:</strong>
                    {payment_status}</p>

                    <p><strong>Paystack Reference:</strong>
                    {order.paystack_reference or "N/A"}</p>

                    <p><strong>Address:</strong>
                    {order.address}</p>

                    <p><strong>Note:</strong>
                    {order.note or "Not provided"}</p>
                """,
            },
            timeout=30,
        )

        print(
            "Resend response:",
            response.status_code,
            response.text
        )

    except Exception as e:
        print("Email error:", e)


# ============================================================
# CREATE ORDER + INITIALIZE PAYSTACK PAYMENT
# ============================================================

class OrderCreateView(APIView):

    def post(self, request):

        serializer = OrderSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        product = data.get("product")
        quantity = data.get("quantity", 1)
        email = data.get("email")

        # ----------------------------------------------------
        # PRODUCTS CURRENTLY AVAILABLE
        # ----------------------------------------------------

        allowed_products = [
            "Pepsi",
            "RC Cola",
            "American Cola",
        ]

        if product not in allowed_products:
            return Response(
                {
                    "success": False,
                    "message": "Invalid product."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----------------------------------------------------
        # EMAIL REQUIRED FOR PAYSTACK
        # ----------------------------------------------------

        if not email:
            return Response(
                {
                    "success": False,
                    "message": "Email is required for online payment."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----------------------------------------------------
        # CALCULATE TOTAL
        # ----------------------------------------------------

        total_amount = PRODUCT_PRICE * quantity

        # ----------------------------------------------------
        # CREATE UNIQUE PAYSTACK REFERENCE
        # ----------------------------------------------------

        reference = (
            f"ARENA-{uuid.uuid4().hex[:16].upper()}"
        )

        # ----------------------------------------------------
        # CREATE PENDING ORDER
        # ----------------------------------------------------

        order = serializer.save(
            amount=total_amount,
            payment_method="online",
            payment_status="pending",
            paystack_reference=reference,
        )

        # ----------------------------------------------------
        # PAYSTACK USES KOBO
        # ₦1,000 = 100,000 KOBO
        # ----------------------------------------------------

        amount_in_kobo = int(total_amount * 100)

        callback_url = config(
            "PAYSTACK_CALLBACK_URL",
            default=(
                "http://127.0.0.1:8000/"
                "api/orders/payment/callback/"
            )
        )

        # ----------------------------------------------------
        # GET PAYSTACK SECRET KEY
        # ----------------------------------------------------

        PAYSTACK_SECRET_KEY = config(
            "PAYSTACK_SECRET_KEY",
            default=""
        )

        if not PAYSTACK_SECRET_KEY:
            order.payment_status = "failed"
            order.save(
                update_fields=["payment_status"]
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "PAYSTACK_SECRET_KEY is missing "
                        "from the backend .env file."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # ----------------------------------------------------
        # INITIALIZE PAYSTACK
        # ----------------------------------------------------

        try:

            response = requests.post(
                "https://api.paystack.co/transaction/initialize",

                headers={
                    "Authorization": (
                        f"Bearer {PAYSTACK_SECRET_KEY}"
                    ),
                    "Content-Type": "application/json",
                },

                json={
                    "email": email,
                    "amount": amount_in_kobo,
                    "currency": "NGN",
                    "reference": reference,
                    "callback_url": callback_url,

                    "metadata": {
                        "order_id": order.id,
                        "full_name": order.full_name,
                        "phone_number": order.phone_number,
                        "email": order.email,
                        "product": order.product,
                        "quantity": order.quantity,
                        "address": order.address,
                        "note": order.note,
                        "amount": float(order.amount),
                    },
                },

                timeout=30,
            )

        except requests.RequestException as e:

            order.payment_status = "failed"
            order.save(
                update_fields=["payment_status"]
            )

            return Response(
                {
                    "success": False,
                    "message": "Unable to connect to Paystack.",
                    "error": str(e),
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        # ----------------------------------------------------
        # READ PAYSTACK RESPONSE
        # ----------------------------------------------------

        try:
            paystack_data = response.json()

        except ValueError:

            order.payment_status = "failed"
            order.save(
                update_fields=["payment_status"]
            )

            return Response(
                {
                    "success": False,
                    "message": "Invalid response received from Paystack.",
                    "response": response.text,
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        # ----------------------------------------------------
        # CHECK PAYSTACK RESPONSE
        # ----------------------------------------------------

        if (
            not response.ok
            or not paystack_data.get("status")
        ):

            order.payment_status = "failed"
            order.save(
                update_fields=["payment_status"]
            )

            return Response(
                {
                    "success": False,
                    "message": paystack_data.get(
                        "message",
                        "Unable to initialize payment."
                    ),
                    "paystack_response": paystack_data,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----------------------------------------------------
        # GET PAYSTACK PAYMENT URL
        # ----------------------------------------------------

        authorization_url = (
            paystack_data
            .get("data", {})
            .get("authorization_url")
        )

        if not authorization_url:

            order.payment_status = "failed"
            order.save(
                update_fields=["payment_status"]
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "Paystack did not return "
                        "a payment URL."
                    ),
                    "paystack_response": paystack_data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        return Response(
            {
                "success": True,
                "message": "Payment initialized successfully.",
                "payment_url": authorization_url,
                "reference": reference,
                "order_id": order.id,
                "amount": float(order.amount),
            },
            status=status.HTTP_200_OK
        )


# ============================================================
# PAYSTACK PAYMENT CALLBACK
# ============================================================

class PaymentCallbackView(APIView):

    def get(self, request):

        reference = request.GET.get("reference")

        if not reference:
            return redirect(
                f"{config('FRONTEND_URL')}"
                "?payment=failed"
            )

        # ----------------------------------------------------
        # GET PAYSTACK SECRET KEY
        # ----------------------------------------------------

        PAYSTACK_SECRET_KEY = config(
            "PAYSTACK_SECRET_KEY",
            default=""
        )

        if not PAYSTACK_SECRET_KEY:
            return redirect(
                f"{config('FRONTEND_URL')}"
                "?payment=failed"
            )

        # ----------------------------------------------------
        # VERIFY PAYMENT WITH PAYSTACK
        # ----------------------------------------------------

        try:

            response = requests.get(
                (
                    "https://api.paystack.co/"
                    f"transaction/verify/{reference}"
                ),

                headers={
                    "Authorization": (
                        f"Bearer {PAYSTACK_SECRET_KEY}"
                    ),
                },

                timeout=30,
            )

        except requests.RequestException:

            return redirect(
                f"{config('FRONTEND_URL')}"
                "?payment=failed"
            )

        try:
            result = response.json()
        except ValueError:
            return redirect(
                f"{config('FRONTEND_URL')}"
                "?payment=failed"
            )

        # ----------------------------------------------------
        # FIND ORDER
        # ----------------------------------------------------

        try:

            order = Order.objects.get(
                paystack_reference=reference
            )

        except Order.DoesNotExist:

            return redirect(
                f"{config('FRONTEND_URL')}"
                "?payment=failed"
            )

        transaction = result.get("data", {})

        transaction_status = transaction.get(
            "status"
        )

        # ----------------------------------------------------
        # SUCCESSFUL PAYMENT
        # ----------------------------------------------------

        if (
            response.ok
            and result.get("status")
            and transaction_status == "success"
        ):

            already_paid = (
                order.payment_status == "paid"
            )

            order.payment_status = "paid"
            order.paid_at = timezone.now()

            order.save(
                update_fields=[
                    "payment_status",
                    "paid_at",
                ]
            )

            # Prevent duplicate emails
            if not already_paid:
                send_order_email(order)

            return redirect(
                f"{config('FRONTEND_URL')}"
                "?payment=success"
            )

        # ----------------------------------------------------
        # FAILED PAYMENT
        # ----------------------------------------------------

        order.payment_status = "failed"

        order.save(
            update_fields=["payment_status"]
        )

        return redirect(
            f"{config('FRONTEND_URL')}"
            "?payment=failed"
        )