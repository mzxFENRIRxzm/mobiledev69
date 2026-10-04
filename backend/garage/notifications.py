from django.db.models import Q, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification


def notify_message(message):
    room = message.conversation
    recipients = set(room.shop.mechanics.filter(is_active=True, groups__name='mechanics')
                     .values_list('pk', flat=True)) | {room.customer_id}
    Notification.objects.bulk_create([
        Notification(recipient_id=pk, conversation=room, message=message,
                     title=f'ข้อความใหม่ · {room.shop.name}'[:240])
        for pk in recipients - {message.sender_id}
    ])


def notify_booking(booking, actor):
    recipients = {booking.customer_id}
    if booking.shop_id:
        recipients.update(booking.shop.mechanics.filter(is_active=True, groups__name='mechanics')
                          .values_list('pk', flat=True))
    elif booking.mechanic_id:
        recipients.add(booking.mechanic_id)
    Notification.objects.bulk_create([
        Notification(recipient_id=pk, booking=booking,
                     title=f'การจอง #{booking.pk} · {booking.get_status_display()}')
        for pk in recipients - {actor.pk}
    ])


def visible_notifications(user):
    # Re-check membership as well as recipient: removed staff must lose access.
    mechanic = not user.is_superuser and user.groups.filter(name='mechanics').exists()
    if mechanic:
        visible = (Q(conversation__shop__mechanics=user) |
                   Q(booking__shop__mechanics=user) |
                   Q(booking__shop__isnull=True, booking__mechanic=user))
    else:
        visible = Q(conversation__customer=user) | Q(booking__customer=user)
    return Notification.objects.filter(visible, recipient=user,
        hidden_at__isnull=True).filter(
        Q(booking__isnull=True) | Q(booking__archived_at__isnull=True)).filter(
        Q(conversation__isnull=True) | Q(conversation__archived_at__isnull=True)).distinct()


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'conversation', 'booking', 'created_at', 'read_at']


class NotificationViewSet(viewsets.ViewSet):
    def list(self, request):
        items = visible_notifications(request.user)
        # Return unread first so old unread items remain reachable in a bounded inbox.
        return Response({
            'unread_count': items.filter(read_at__isnull=True).count(),
            'latest_id': items.order_by('-pk').values_list('pk', flat=True).first() or 0,
            'results': NotificationSerializer(
                items.order_by(F('read_at').asc(nulls_first=True), '-pk')[:100], many=True).data,
        })

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        item = get_object_or_404(visible_notifications(request.user), pk=pk)
        Notification.objects.filter(pk=item.pk, read_at__isnull=True).update(read_at=timezone.now())
        return Response({'ok': True})

    @action(detail=False, methods=['post'], url_path='read-all')
    def read_all(self, request):
        class Boundary(serializers.Serializer):
            through_id = serializers.IntegerField(min_value=0)
        data = Boundary(data=request.data)
        data.is_valid(raise_exception=True)
        visible_notifications(request.user).filter(
            pk__lte=data.validated_data['through_id'], read_at__isnull=True,
        ).update(read_at=timezone.now())
        return Response({'ok': True})
