from django.db import transaction
from django.db.models import Q, Count, OuterRef, Subquery, F
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .bookings import is_mechanic
from .models import Shop, ShopConversation, ShopMessage
from .notifications import notify_message, visible_notifications


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.username", read_only=True)

    class Meta:
        model = ShopMessage
        fields = ["id", "sender", "sender_name", "body", "created_at"]
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    unread_count = serializers.IntegerField(read_only=True, default=0)
    last_message = serializers.CharField(read_only=True, default='')
    last_message_at = serializers.DateTimeField(read_only=True, default=None)
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    customer_name = serializers.CharField(source="customer.username", read_only=True)

    class Meta:
        model = ShopConversation
        fields = ["id", "shop", "shop_name", "customer", "customer_name", "created_at",
                  "unread_count", "last_message", "last_message_at"]
        read_only_fields = fields


class CreateConversationSerializer(serializers.Serializer):
    shop = serializers.PrimaryKeyRelatedField(
        queryset=Shop.objects.filter(awaiting_owner_verification=False)
    )


class SendMessageSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)
    request_id = serializers.UUIDField(required=False)


class MessageThrottle(UserRateThrottle):
    rate = "60/min"


class ConversationViewSet(viewsets.ViewSet):
    def _visible(self, request):
        user = request.user
        visible = Q(shop__mechanics=user) if is_mechanic(user) else Q(customer=user)
        return ShopConversation.objects.filter(visible).distinct().select_related("shop", "customer")

    def list(self, request):
        latest = ShopMessage.objects.filter(conversation_id=OuterRef('pk')).order_by('-pk')
        conversations = self._visible(request).annotate(
            unread_count=Count('notification', filter=Q(
                notification__recipient=request.user, notification__read_at__isnull=True)),
            last_message=Subquery(latest.values('body')[:1]),
            last_message_at=Subquery(latest.values('created_at')[:1]),
            last_message_id=Subquery(latest.values('pk')[:1]),
        ).order_by(F('last_message_id').desc(nulls_last=True), '-pk')
        return Response(ConversationSerializer(conversations, many=True).data)

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        room = get_object_or_404(self._visible(request), pk=pk)
        class Boundary(serializers.Serializer):
            through_message = serializers.IntegerField(min_value=1)
        data = Boundary(data=request.data)
        data.is_valid(raise_exception=True)
        boundary = get_object_or_404(room.messages, pk=data.validated_data['through_message'])
        visible_notifications(request.user).filter(
            conversation=room, message_id__lte=boundary.pk, read_at__isnull=True,
        ).update(read_at=timezone.now())
        return Response({'ok': True})

    def create(self, request):
        if is_mechanic(request.user) or request.user.is_superuser:
            raise PermissionDenied("เฉพาะลูกค้าเริ่มแชตกับร้านได้")
        serializer = CreateConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            conversation, _ = ShopConversation.objects.get_or_create(
                shop=serializer.validated_data["shop"], customer=request.user
            )
        return Response(ConversationSerializer(conversation).data, status=201)

    @action(detail=True, methods=["get", "post"], throttle_classes=[MessageThrottle])
    def messages(self, request, pk=None):
        conversation = get_object_or_404(self._visible(request), pk=pk)
        if request.method == "GET":
            from .history import history_page
            return Response(history_page(conversation.messages.select_related("sender"), request,
                                         lambda rows: MessageSerializer(rows, many=True).data))
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            values = serializer.validated_data
            if values.get('request_id'):
                message, created = ShopMessage.objects.get_or_create(
                    conversation=conversation, sender=request.user, request_id=values['request_id'],
                    defaults={'body': values['body']})
                if message.body != values['body']:
                    raise serializers.ValidationError('request_id นี้ถูกใช้กับข้อความอื่นแล้ว')
            else:
                message = ShopMessage.objects.create(conversation=conversation, sender=request.user, body=values['body'])
                created = True
            if created:
                notify_message(message)
        return Response(MessageSerializer(message).data, status=201 if created else 200)
