from django.db import models
from django.utils.translation import gettext_lazy as _


class UserType(models.TextChoices):
    buyer = 'buyer', _('Buyer')
    seller = 'seller', _('Seller')


class UserConfirmation(models.TextChoices):
    need_user = 2, _("Confirmation of the user's status is required")
    need_admin = 1, _('Confirmation of the admin status is required')
    confirmed = 0, _('Confirmed')


class SellerOrderState(models.TextChoices):
    basket = 'basket', _('Basket status')
    new = 'new', _('New')
    confirmed = 'confirmed', _('Confirmed')
    assembled = 'assembled', _('Assembled')
    sent = 'sent', _('Shipped')
    delivered = 'delivered', _('Delivered')
    canceled = 'canceled', _('Canceled')

    @classmethod
    def get_cancelable_by_user_states(cls):
        return {cls.basket, cls.new, cls.confirmed, cls.assembled}


class BuyerOrderState(models.TextChoices):
    basket = 'basket', _('Basket status')
    partial_accepted = 'partial accepted', _('Partially accepted')
    accepted = 'accepted', _('Accepted')


class PartnerState(models.TextChoices):
    open = 'open', _('Open')
    closed = 'closed', _('Closed')
