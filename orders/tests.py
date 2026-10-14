from decimal import Decimal
from unittest.mock import Mock, patch

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Order


class OrderCreateViewTests(APITestCase):
    url = "/api/orders/create/"

    def setUp(self):
        self.order_data = {
            "full_name": "Test Customer",
            "phone_number": "08012345678",
            "email": "customer@example.com",
            "product": "Zobo",
            "quantity": 1,
            "address": "1 Test Street",
        }

    @patch("orders.views.config", return_value="test-secret")
    @patch("orders.views.requests.post")
    def test_zobo_order_uses_promotional_price(self, post_payment, _config):
        payment_response = Mock()
        payment_response.ok = True
        payment_response.json.return_value = {
            "status": "success",
            "data": {"link": "https://payments.example/checkout"},
        }
        post_payment.return_value = payment_response

        response = self.client.post(self.url, self.order_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["amount"], 2500.0)
        order = Order.objects.get(pk=response.data["order_id"])
        self.assertEqual(order.product, "Zobo")
        self.assertEqual(order.amount, Decimal("2500.00"))
        self.assertEqual(response.data["reference"], order.tx_ref)
        self.assertEqual(
            post_payment.call_args.kwargs["json"]["amount"],
            "2500",
        )

    def test_old_products_are_rejected_for_new_orders(self):
        for product in ("Pepsi", "American Cola", "Aristocrat", "RC Cola"):
            with self.subTest(product=product):
                response = self.client.post(
                    self.url,
                    {**self.order_data, "product": product},
                    format="json",
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                )
                self.assertIn("product", response.data)

        self.assertEqual(Order.objects.count(), 0)
