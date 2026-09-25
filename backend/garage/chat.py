from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .bookings import is_mechanic
from .models import Shop, ShopConversation, ShopMessage


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.username", read_only=True)

    class Meta:
        model = ShopMessage
        fields = ["id", "sender", "sender_name", "body", "created_at"]
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    customer_name = serializers.CharField(source="customer.username", read_only=True)

    class Meta:
        model = ShopConversation
        fields = ["id", "shop", "shop_name", "customer", "customer_name", "created_at"]
        read_only_fields = fields


class CreateConversationSerializer(serializers.Serializer):
    shop = serializers.PrimaryKeyRelatedField(
        queryset=Shop.objects.filter(awaiting_owner_verification=False)
    )


class SendMessageSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)


class MessageThrottle(UserRateThrottle):
    rate = "60/min"


class ConversationViewSet(viewsets.ViewSet):
    def _visible(self, request):
        user = request.user
        visible = Q(shop__mechanics=user) if is_mechanic(user) else Q(customer=user)
        return ShopConversation.objects.filter(visible).distinct().select_related("shop", "customer")

    def list(self, request):
        conversations = self._visible(request).order_by("-pk")
        return Response(ConversationSerializer(conversations, many=True).data)

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
            messages = conversation.messages.select_related("sender").order_by("-pk")[:100]
            return Response(MessageSerializer(reversed(list(messages)), many=True).data)
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = ShopMessage.objects.create(
            conversation=conversation, sender=request.user, body=serializer.validated_data["body"]
        )
        return Response(MessageSerializer(message).data, status=201)
