"""One shop visibility rule shared by discovery, booking and messaging."""

from django.db.models import Q
from django.utils import timezone

from .models import Shop


def available_shops():
    return Shop.objects.filter(awaiting_owner_verification=False).filter(
        Q(moderation_status=Shop.ModerationStatus.ACTIVE) |
        Q(moderation_status=Shop.ModerationStatus.SUSPENDED,
          suspended_until__lte=timezone.now()))


def shop_available(shop):
    return not shop.awaiting_owner_verification and (
        shop.moderation_status == Shop.ModerationStatus.ACTIVE or
        (shop.moderation_status == Shop.ModerationStatus.SUSPENDED and
         shop.suspended_until is not None and shop.suspended_until <= timezone.now()))
