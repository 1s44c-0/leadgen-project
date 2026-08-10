from django.urls import path
from .views import OrderCreateView, PaymentLinkView

urlpatterns = [
    path('create/', OrderCreateView.as_view(), name='create-order'),
    path('payment-link/', PaymentLinkView.as_view(), name='payment-link'),
]