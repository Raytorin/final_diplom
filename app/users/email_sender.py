from django.core.mail import EmailMessage, send_mail
from orders.settings import EMAIL_HOST_USER


def send_confirmation_email(*emails, subject: str, message: str):
    email = EmailMessage(subject=subject,
                         body=message,
                         from_email=EMAIL_HOST_USER,
                         to=[emails],
                         headers={'From': f'{EMAIL_HOST_USER}'})

    email.send()

# def send_confirmation_email(*emails, subject: str, message: str):
#     email = send_mail(
#         subject,
#         message,
#         EMAIL_HOST_USER,
#         [emails],
#         fail_silently=False,
#     )
#
#     email.send()
