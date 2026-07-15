from django.core.mail import send_mail
from django.conf import settings

def send_test_email():
    send_mail(
        subject='New Order Notification',
        message='Hello, a new order has been placed. Please check the admin panel for details.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=['holorunphemyhyzik@gmail.com'],
        fail_silently=False,
    )
