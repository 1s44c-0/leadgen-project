from django.urls import path

from .views import (
    OrderCreateView,
    PaymentCallbackView,
)

urlpatterns = [
    path(
        "create/",
        OrderCreateView.as_view(),
        name="create-order",
    ),

    path(
        "payment/callback/",
        PaymentCallbackView.as_view(),
        name="payment-callback",
    ),
]