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

PRODUCT_PRICE = 1500  # ₦1,500 per unit


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

                    <p><strong>Flutterwave Reference:</strong>
                    {order.tx_ref or "N/A"}</p>

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
# CREATE ORDER + INITIALIZE FLUTTERWAVE PAYMENT
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
        # EMAIL REQUIRED FOR FLUTTERWAVE
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
        # CREATE UNIQUE TRANSACTION REFERENCE
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
            tx_ref=reference,
        )

        # ----------------------------------------------------
        # NOTE: unlike Paystack, Flutterwave takes the amount
        # in the main currency unit (e.g. 1000 = ₦1,000), NOT
        # in kobo. Do not multiply by 100 here.
        # ----------------------------------------------------

        redirect_url = config(
            "FLW_REDIRECT_URL",
            default=(
                "http://127.0.0.1:8000/"
                "api/orders/payment/callback/"
            )
        )

        # ----------------------------------------------------
        # GET FLUTTERWAVE SECRET KEY
        # ----------------------------------------------------

        FLW_SECRET_KEY = config(
            "FLW_SECRET_KEY",
            default=""
        )

        if not FLW_SECRET_KEY:
            order.payment_status = "failed"
            order.save(
                update_fields=["payment_status"]
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "FLW_SECRET_KEY is missing "
                        "from the backend .env file."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # ----------------------------------------------------
        # INITIALIZE FLUTTERWAVE PAYMENT
        # ----------------------------------------------------

        try:

            response = requests.post(
                "https://api.flutterwave.com/v3/payments",

                headers={
                    "Authorization": (
                        f"Bearer {FLW_SECRET_KEY}"
                    ),
                    "Content-Type": "application/json",
                },

                json={
                    "tx_ref": reference,
                    "amount": str(total_amount),
                    "currency": "NGN",
                    "redirect_url": redirect_url,

                    "customer": {
                        "email": email,
                        "phonenumber": order.phone_number,
                        "name": order.full_name,
                    },

                    "customizations": {
                        "title": "Arena Ventures Order",
                        "description": f"Payment for {product}",
                    },

                    "meta": {
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
                    "message": "Unable to connect to Flutterwave.",
                    "error": str(e),
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        # ----------------------------------------------------
        # READ FLUTTERWAVE RESPONSE
        # ----------------------------------------------------

        try:
            flw_data = response.json()

        except ValueError:

            order.payment_status = "failed"
            order.save(
                update_fields=["payment_status"]
            )

            return Response(
                {
                    "success": False,
                    "message": "Invalid response received from Flutterwave.",
                    "response": response.text,
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        # ----------------------------------------------------
        # CHECK FLUTTERWAVE RESPONSE
        # ----------------------------------------------------

        if (
            not response.ok
            or flw_data.get("status") != "success"
        ):

            order.payment_status = "failed"
            order.save(
                update_fields=["payment_status"]
            )

            return Response(
                {
                    "success": False,
                    "message": flw_data.get(
                        "message",
                        "Unable to initialize payment."
                    ),
                    "flutterwave_response": flw_data,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----------------------------------------------------
        # GET FLUTTERWAVE PAYMENT LINK
        # ----------------------------------------------------

        authorization_url = (
            flw_data
            .get("data", {})
            .get("link")
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
                        "Flutterwave did not return "
                        "a payment link."
                    ),
                    "flutterwave_response": flw_data,
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
# FLUTTERWAVE PAYMENT CALLBACK
# ============================================================

class PaymentCallbackView(APIView):

    def get(self, request):

        tx_ref = request.GET.get("tx_ref")
        flw_status = request.GET.get("status")  # successful | cancelled | failed

        if not tx_ref:
            return redirect(
                f"{config('FRONTEND_URL')}"
                "?payment=failed"
            )

        # ----------------------------------------------------
        # FIND ORDER
        # ----------------------------------------------------

        try:

            order = Order.objects.get(
                tx_ref=tx_ref
            )

        except Order.DoesNotExist:

            return redirect(
                f"{config('FRONTEND_URL')}"
                "?payment=failed"
            )

        # ----------------------------------------------------
        # IF THE USER CANCELLED ON FLUTTERWAVE'S PAGE,
        # NO NEED TO VERIFY - JUST MARK AS FAILED
        # ----------------------------------------------------

        if flw_status == "cancelled":

            order.payment_status = "failed"
            order.save(
                update_fields=["payment_status"]
            )

            return redirect(
                f"{config('FRONTEND_URL')}"
                "?payment=failed"
            )

        # ----------------------------------------------------
        # GET FLUTTERWAVE SECRET KEY
        # ----------------------------------------------------

        FLW_SECRET_KEY = config(
            "FLW_SECRET_KEY",
            default=""
        )

        if not FLW_SECRET_KEY:
            return redirect(
                f"{config('FRONTEND_URL')}"
                "?payment=failed"
            )

        # ----------------------------------------------------
        # VERIFY PAYMENT WITH FLUTTERWAVE
        # (verify by our own tx_ref, never trust the querystring
        # status/amount on their own)
        # ----------------------------------------------------

        try:

            response = requests.get(
                (
                    "https://api.flutterwave.com/v3/"
                    "transactions/verify_by_reference"
                ),

                params={
                    "tx_ref": tx_ref,
                },

                headers={
                    "Authorization": (
                        f"Bearer {FLW_SECRET_KEY}"
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

        transaction = result.get("data", {})

        transaction_status = transaction.get("status")
        transaction_amount = transaction.get("amount")
        transaction_currency = transaction.get("currency")

        # ----------------------------------------------------
        # SUCCESSFUL PAYMENT
        # Confirm status, amount, and currency all match to
        # guard against tampering.
        # ----------------------------------------------------

        if (
            response.ok
            and result.get("status") == "success"
            and transaction_status == "successful"
            and transaction_currency == "NGN"
            and transaction_amount is not None
            and float(transaction_amount) >= float(order.amount)
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
