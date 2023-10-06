from django.core.mail import EmailMessage
from project_orders.settings import EMAIL_HOST_USER


def send_confirmation_email(*emails, subject: str, message: str):
    email = EmailMessage(subject=subject,
                         body=message,
                         from_email=EMAIL_HOST_USER,
                         to=emails)
    email.send()
