from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, NotFound
from rest_framework.response import Response
from .models import Booking, BookingEvent, Motorcycle, Shop


def is_mechanic(user):
    return not user.is_superuser and user.groups.filter(name="mechanics").exists()


class Conflict(APIException):
    status_code = 409
    default_detail = "สถานะงานเปลี่ยนแล้ว กรุณาโหลดใหม่"


class BookingEventSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username", read_only=True)
    class Meta:
        model = BookingEvent
        fields = ["status", "actor", "created_at"]


class BookingSerializer(serializers.ModelSerializer):
    shop = serializers.PrimaryKeyRelatedField(queryset=Shop.objects.filter(accepting_bookings=True), required=True, allow_null=False)
    customer_name = serializers.CharField(source="customer.username", read_only=True)
    mechanic_name = serializers.CharField(source="mechanic.username", read_only=True, default=None)
    events = BookingEventSerializer(many=True, read_only=True)
    class Meta:
        model = Booking
        fields = ["id", "shop", "shop_name", "cancellation_reason", "motorcycle", "motorcycle_label", "customer_name", "mechanic_name",
                  "appointment_at", "problem", "status", "repair_notes", "created_at", "updated_at", "events"]
        read_only_fields = ["id", "shop_name", "cancellation_reason", "motorcycle_label", "status", "repair_notes", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        self.fields["motorcycle"].queryset = Motorcycle.objects.filter(owner=request.user) if request else Motorcycle.objects.none()

    def validate_appointment_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("กรุณาเลือกวันเวลาในอนาคต")
        return value


class TransitionSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    action = serializers.ChoiceField(choices=["accept", "start", "complete", "cancel"])
    repair_notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class BookingViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = BookingSerializer

    def get_queryset(self):
        user = self.request.user
        if is_mechanic(user):
            visible = Q(shop__mechanics=user) | Q(shop__isnull=True, mechanic=user)
        else:
            visible = Q(customer=user)
        return Booking.objects.filter(visible).distinct().select_related("customer", "mechanic").prefetch_related("events__actor")

    def perform_create(self, serializer):
        if is_mechanic(self.request.user):
            raise PermissionDenied("บัญชีช่างใช้สำหรับรับและจัดการงานซ่อม")
        try:
            with transaction.atomic():
                shop = Shop.objects.select_for_update().get(pk=serializer.validated_data["shop"].pk)
                if not shop.accepting_bookings:
                    raise Conflict("ร้านนี้ปิดรับการจองแล้ว กรุณาเลือกร้านอื่น")
                bike = Motorcycle.objects.select_for_update().get(pk=serializer.validated_data["motorcycle"].pk, owner=self.request.user)
                booking = serializer.save(customer=self.request.user, shop_name=shop.name,
                    motorcycle_label=f"{bike.brand} {bike.model} · {bike.license_plate}")
                BookingEvent.objects.create(booking=booking, actor=self.request.user, status=booking.status)
        except (Motorcycle.DoesNotExist, Shop.DoesNotExist):
            raise serializers.ValidationError("ไม่พบรถที่ต้องการจอง กรุณาโหลดใหม่")
        except IntegrityError:
            raise Conflict("รถคันนี้มีรายการซ่อมที่ยังไม่จบอยู่แล้ว")

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        data = TransitionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        command = data.validated_data["action"]
        with transaction.atomic():
            # Lock the booking row itself, without a nullable outer join.
            booking = get_object_or_404(Booking.objects.select_for_update(), pk=pk)
            mechanic = is_mechanic(request.user)
            if mechanic:
                if booking.shop_id:
                    if not Shop.objects.filter(pk=booking.shop_id, mechanics=request.user).exists():
                        raise NotFound()
                elif booking.mechanic_id != request.user.pk:
                    raise NotFound()
            if not mechanic and booking.customer_id != request.user.pk:
                raise NotFound()
            if command == "cancel":
                reason = data.validated_data.get("cancellation_reason", "").strip()
                if mechanic and not reason:
                    raise serializers.ValidationError({"cancellation_reason": "กรุณาระบุเหตุผลที่ร้านไม่พร้อมให้บริการ"})
                if booking.status not in [Booking.Status.PENDING, Booking.Status.ACCEPTED]:
                    raise Conflict("ยกเลิกได้เฉพาะงานที่ยังไม่เริ่มซ่อม")
                booking.cancellation_reason = reason
                target = Booking.Status.CANCELLED
            else:
                if not mechanic:
                    raise PermissionDenied("เฉพาะช่างที่ได้รับสิทธิ์เท่านั้น")
                if booking.customer_id == request.user.pk:
                    raise PermissionDenied("ไม่สามารถรับงานของตัวเองได้")
                if command == "accept":
                    if booking.status != Booking.Status.PENDING or booking.mechanic_id:
                        raise Conflict()
                    booking.mechanic = request.user
                    target = Booking.Status.ACCEPTED
                else:
                    if booking.mechanic_id != request.user.pk:
                        raise PermissionDenied("งานนี้ไม่ได้มอบหมายให้คุณ")
                    expected, target = {
                        "start": (Booking.Status.ACCEPTED, Booking.Status.IN_PROGRESS),
                        "complete": (Booking.Status.IN_PROGRESS, Booking.Status.COMPLETED),
                    }[command]
                    if booking.status != expected:
                        raise Conflict()
                    if command == "complete":
                        notes = data.validated_data.get("repair_notes", "").strip()
                        if not notes:
                            raise serializers.ValidationError({"repair_notes": "กรุณาระบุรายละเอียดงานซ่อม"})
                        booking.repair_notes = notes
            booking.status = target
            booking.save()
            BookingEvent.objects.create(booking=booking, actor=request.user, status=target)
        return Response(self.get_serializer(booking).data)
