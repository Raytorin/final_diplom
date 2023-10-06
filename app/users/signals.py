from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.dispatch import receiver
from django_rest_passwordreset.signals import reset_password_token_created, post_password_reset
from django_rest_passwordreset.views import ResetPasswordRequestToken
from .views import CustomResetPasswordConfirm


@receiver(post_password_reset, sender=CustomResetPasswordConfirm)
def auth_token_reset(sender, user, **kwargs):
    user.update_auth_token()


@receiver(reset_password_token_created, sender=ResetPasswordRequestToken)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    msg = EmailMultiAlternatives(
        f"Password Reset Token for {reset_password_token.user}",
        reset_password_token.key,
        settings.EMAIL_HOST_USER,
        [reset_password_token.user.email]
    )
    msg.send()


@receiver(post_password_reset, sender=CustomResetPasswordConfirm)
def auth_token_reset(sender, user, **kwargs):
    user.update_auth_token()
