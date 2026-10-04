"""OIDC-protected administration for the Flutter app."""

import base64
import hashlib
import json
import logging
import math
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5

import psycopg
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .models import (AdminAuditEvent, AiEmbeddingCredential, Booking, BookingEvent, Motorcycle,
                     MotorcycleKnowledge, Shop, UserProfile)
from .notifications import notify_booking
from .roles import role_for
from .registration import validate_unique_email
from .uploads import clean_shop_photo
from .shop_visibility import shop_available

logger = logging.getLogger(__name__)
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSIONS = 3072


class AdminUnavailable(APIException):
    status_code = 503
    default_detail = "บริการ embedding ยังไม่พร้อมใช้งาน กรุณาตรวจการตั้งค่าเซิร์ฟเวอร์"


class KnowledgeChanged(APIException):
    status_code = 409
    default_detail = "ข้อมูลรถเปลี่ยนระหว่างทำ embedding กรุณาลองใหม่"


class EmbeddingThrottle(UserRateThrottle):
    rate = "8/min"


def require_admin(request):
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied("เฉพาะ Adminuser")


def private(data, status=200):
    response = Response(data, status=status)
    response["Cache-Control"] = "no-store"
    return response


def credential_cipher():
    # A distinct derived encryption key keeps the API key out of the Django DB
    # and avoids requiring another secret in existing deployments.
    digest = hashlib.sha256(b"the_x_embedding_key_v1:" + settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def credential_info():
    row = AiEmbeddingCredential.objects.order_by("pk").first()
    return {"configured": row is not None, "hint": row.key_hint if row else "",
            "updated_at": row.updated_at.isoformat() if row else None}


class KeyInput(serializers.Serializer):
    api_key = serializers.CharField(min_length=15, max_length=512, trim_whitespace=True, write_only=True)


class RoleInput(serializers.Serializer):
    role = serializers.ChoiceField(choices=["customer", "mechanic", "admin"], required=False)
    is_active = serializers.BooleanField(required=False)
    username = serializers.RegexField(r'^[\w.@+-]+$', max_length=150, required=False)
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    email = serializers.EmailField(max_length=254, allow_blank=True, required=False)
    phone = serializers.RegexField(r'^\+?[0-9]{9,15}$', max_length=20,
                                   allow_blank=True, required=False)


class KnowledgeInput(serializers.ModelSerializer):
    class Meta:
        model = MotorcycleKnowledge
        fields = ["brand", "model", "year", "section", "content", "source_url", "reviewed"]

    def validate_source_url(self, value):
        if not value.startswith("https://"):
            raise serializers.ValidationError("แหล่งข้อมูลต้องใช้ HTTPS")
        return value


class KnowledgeArchiveInput(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=500, trim_whitespace=True)


class ShopMechanicsInput(serializers.Serializer):
    mechanic_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=0, max_length=100)

    def validate_mechanic_ids(self, values):
        if len(values) != len(set(values)):
            raise serializers.ValidationError("มีช่างซ้ำในรายการ")
        users = get_user_model().objects.filter(pk__in=values, is_active=True,
                                                groups__name="mechanics", is_superuser=False)
        if users.count() != len(values):
            raise serializers.ValidationError("เลือกได้เฉพาะผู้ใช้บทบาทช่างที่ใช้งานอยู่")
        return values


def knowledge_data(row):
    return {"id": row.pk, "brand": row.brand, "model": row.model,
            "year": row.year, "section": row.section, "content": row.content,
            "source_url": row.source_url, "reviewed": row.reviewed,
            "embedding_status": row.embedding_status,
            "embedded_at": row.embedded_at.isoformat() if row.embedded_at else None,
            "updated_at": row.updated_at.isoformat()}


@api_view(["GET"])
def admin_overview(request):
    require_admin(request)
    User = get_user_model()
    return private({"users": User.objects.count(), "shops": Shop.objects.count(),
                    "pending_shops": Shop.objects.filter(awaiting_owner_verification=True).count(),
                    "bookings": Booking.objects.count(),
                    "active_bookings": Booking.objects.filter(status__in=[
                        Booking.Status.PENDING, Booking.Status.ACCEPTED,
                        Booking.Status.IN_PROGRESS]).count(),
                    "knowledge": MotorcycleKnowledge.objects.filter(archived_at__isnull=True).count(),
                    "embedded": MotorcycleKnowledge.objects.filter(
                        archived_at__isnull=True, embedding_status="ready").count(),
                    "embedding_key": credential_info()})


@api_view(["GET"])
def admin_users(request):
    require_admin(request)
    users = get_user_model().objects.select_related("profile")
    query = request.query_params.get("q", "").strip()[:100]
    if query:
        users = users.filter(Q(username__icontains=query) | Q(first_name__icontains=query) |
                             Q(last_name__icontains=query) | Q(email__icontains=query) |
                             Q(profile__phone__icontains=query))
    users = users.order_by("-date_joined", "-pk")[:100]
    return private([user_data(u) for u in users])


def user_data(user):
    profile = getattr(user, "profile", None)
    return {"id": user.pk, "username": user.username, "first_name": user.first_name,
            "last_name": user.last_name, "email": user.email,
            "phone": profile.phone if profile else "",
            "role": role_for(user), "is_active": user.is_active}


@api_view(["GET"])
def admin_audit(request):
    require_admin(request)
    rows = AdminAuditEvent.objects.select_related("actor")[:100]
    return private([{"id": row.pk, "actor": row.actor.username, "action": row.action,
                     "target_type": row.target_type, "target_id": row.target_id,
                     "details": row.details, "created_at": row.created_at.isoformat()}
                    for row in rows])


@api_view(["GET", "PATCH"])
def admin_user(request, pk):
    require_admin(request)
    if request.method == "GET":
        return private(user_data(get_object_or_404(
            get_user_model().objects.select_related("profile"), pk=pk)))
    incoming = RoleInput(data=request.data)
    incoming.is_valid(raise_exception=True)
    with transaction.atomic():
        User = get_user_model()
        # Lock the complete administrator set to serialize final-admin edits.
        list(User.objects.select_for_update().filter(is_superuser=True).order_by("pk"))
        user = get_object_or_404(User.objects.select_for_update(), pk=pk)
        values = incoming.validated_data
        if "username" in values and User.objects.filter(username__iexact=values["username"]).exclude(pk=pk).exists():
            raise serializers.ValidationError({"username": "ชื่อผู้ใช้นี้ถูกใช้แล้ว"})
        if "email" in values:
            try:
                values["email"] = validate_unique_email(values["email"], pk)
            except DjangoValidationError as error:
                raise serializers.ValidationError({"email": "อีเมลนี้ถูกใช้แล้ว"}) from error
        role = incoming.validated_data.get("role", role_for(user))
        active = incoming.validated_data.get("is_active", user.is_active)
        if user.is_superuser and (role != "admin" or not active):
            if not User.objects.filter(is_superuser=True, is_active=True).exclude(pk=pk).exists():
                raise serializers.ValidationError({"role": "ต้องเหลือ Adminuser ที่ใช้งานได้อย่างน้อยหนึ่งคน"})
        if role != role_for(user) and user.repair_jobs.filter(status__in=[
            Booking.Status.ACCEPTED, Booking.Status.IN_PROGRESS]).exists():
            raise serializers.ValidationError({"role": "ต้องปิดงานซ่อมที่รับไว้ก่อนเปลี่ยนบทบาท"})
        email_changed = "email" in values and values["email"] != user.email
        for field in ("username", "first_name", "last_name", "email"):
            if field in values:
                setattr(user, field, values[field])
        user.is_active = active
        user.is_staff = user.is_superuser = role == "admin"
        user.save(update_fields=["is_active", "is_staff", "is_superuser", *(
            field for field in ("username", "first_name", "last_name", "email") if field in values)])
        if "phone" in values or email_changed:
            profile, _ = UserProfile.objects.select_for_update().get_or_create(
                user=user, defaults={"phone": values.get("phone", "")})
            if "phone" in values:
                profile.phone = values["phone"]
            if email_changed:
                profile.pending_email = ""
                profile.email_verified_at = None
            profile.save()
        if "role" in incoming.validated_data:
            user.groups.clear()
            user.user_permissions.clear()
            if role == "mechanic":
                group, _ = Group.objects.get_or_create(name="mechanics")
                user.groups.add(group)
            else:
                user.service_shops.clear()
        AdminAuditEvent.objects.create(actor=request.user, action="user_updated",
            target_type="user", target_id=pk,
            details={"role": role, "is_active": active, "fields": sorted(values)})
    logger.info("Admin %s updated user %s role=%s active=%s", request.user.pk, pk, role, active)
    return private(user_data(user))


class AdminMotorcycleInput(serializers.ModelSerializer):
    class Meta:
        model = Motorcycle
        fields = ["brand", "model", "license_plate", "year", "mileage", "notes"]

    def validate_license_plate(self, value):
        value = value.strip().upper()
        if Motorcycle.objects.filter(owner=self.instance.owner,
            license_plate=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("ทะเบียนนี้มีอยู่แล้วในโรงรถของผู้ใช้")
        return value


def motorcycle_data(row):
    return {"id": row.pk, "brand": row.brand, "model": row.model,
            "license_plate": row.license_plate, "year": row.year,
            "mileage": row.mileage, "notes": row.notes,
            "archived_at": row.archived_at.isoformat() if row.archived_at else None,
            "archive_reason": row.archive_reason}


@api_view(["GET"])
def admin_user_motorcycles(request, pk):
    require_admin(request)
    get_object_or_404(get_user_model(), pk=pk)
    rows = Motorcycle.objects.filter(owner_id=pk).order_by("-created_at")[:100]
    return private([motorcycle_data(row) for row in rows])


@api_view(["GET", "PATCH"])
def admin_user_motorcycle(request, pk, motorcycle_pk):
    require_admin(request)
    if request.method == "GET":
        return private(motorcycle_data(get_object_or_404(
            Motorcycle, pk=motorcycle_pk, owner_id=pk)))
    with transaction.atomic():
        row = get_object_or_404(Motorcycle.objects.select_for_update(), pk=motorcycle_pk,
                                owner_id=pk)
        if row.archived_at:
            raise serializers.ValidationError("รถที่ซ่อนแล้วแก้ไขไม่ได้")
        incoming = AdminMotorcycleInput(row, data=request.data, partial=True)
        incoming.is_valid(raise_exception=True)
        row = incoming.save()
        AdminAuditEvent.objects.create(actor=request.user, action="motorcycle_updated",
            target_type="motorcycle", target_id=row.pk,
            details={"owner_id": pk, "fields": sorted(incoming.validated_data)})
    return private(motorcycle_data(row))


class AdminArchiveInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=["archive", "restore"])
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)

    def validate(self, values):
        if values["action"] == "archive" and not values.get("reason", "").strip():
            raise serializers.ValidationError({"reason": "กรุณาระบุเหตุผล"})
        return values


@api_view(["POST"])
def admin_user_motorcycle_archive(request, pk, motorcycle_pk):
    require_admin(request)
    incoming = AdminArchiveInput(data=request.data)
    incoming.is_valid(raise_exception=True)
    action = incoming.validated_data["action"]
    with transaction.atomic():
        row = get_object_or_404(Motorcycle.objects.select_for_update(), pk=motorcycle_pk,
                                owner_id=pk)
        if action == "archive" and Booking.objects.filter(motorcycle=row,
            status__in=[Booking.Status.PENDING, Booking.Status.ACCEPTED,
                        Booking.Status.IN_PROGRESS], archived_at__isnull=True).exists():
            raise serializers.ValidationError("ต้องปิดงานซ่อมที่กำลังดำเนินอยู่ก่อนซ่อนรถ")
        row.archived_at = timezone.now() if action == "archive" else None
        row.archive_reason = incoming.validated_data.get("reason", "").strip() if action == "archive" else ""
        row.save(update_fields=["archived_at", "archive_reason"])
        AdminAuditEvent.objects.create(actor=request.user, action=f"motorcycle_{action}",
            target_type="motorcycle", target_id=row.pk,
            details={"owner_id": pk, "reason": row.archive_reason})
    return private(motorcycle_data(row))


@api_view(["GET"])
def admin_shops(request):
    require_admin(request)
    rows = Shop.objects.prefetch_related("mechanics")
    query = request.query_params.get("q", "").strip()[:100]
    if query:
        rows = rows.filter(Q(name__icontains=query) | Q(address__icontains=query) |
                           Q(phone__icontains=query))
    rows = rows.order_by("name", "pk")[:100]
    return private([shop_data(row) for row in rows])


def shop_data(row):
    return {"id": row.pk, "name": row.name, "address": row.address,
            "phone": row.phone, "description": row.description,
            "photo": row.photo.url if row.photo else None,
            "latitude": str(row.latitude) if row.latitude is not None else None,
            "longitude": str(row.longitude) if row.longitude is not None else None,
            "mechanic_count": len(row.mechanics.all()),
            "mechanic_ids": [u.pk for u in row.mechanics.all()],
            "awaiting_owner_verification": row.awaiting_owner_verification,
            "accepting_bookings": row.accepting_bookings,
            "moderation_status": row.moderation_status,
            "suspended_until": row.suspended_until.isoformat() if row.suspended_until else None,
            "moderation_reason": row.moderation_reason,
            "available": shop_available(row)}


class AdminShopInput(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ["name", "address", "phone", "description", "photo", "latitude",
                  "longitude", "accepting_bookings"]

    def validate_photo(self, value):
        try:
            return clean_shop_photo(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error

    def validate(self, values):
        latitude = values.get("latitude", self.instance.latitude)
        longitude = values.get("longitude", self.instance.longitude)
        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError({"latitude": "ต้องมีพิกัดทั้งสองค่าหรือไม่ระบุเลย"})
        return values


@api_view(["GET", "PATCH"])
def admin_shop_details(request, pk):
    require_admin(request)
    if request.method == "GET":
        return private(shop_data(get_object_or_404(
            Shop.objects.prefetch_related("mechanics"), pk=pk)))
    with transaction.atomic():
        row = get_object_or_404(Shop.objects.select_for_update(), pk=pk)
        if row.moderation_status == Shop.ModerationStatus.DELETED:
            raise serializers.ValidationError("ร้านที่ลบถาวรแก้ไขข้อมูลไม่ได้")
        incoming = AdminShopInput(row, data=request.data, partial=True)
        incoming.is_valid(raise_exception=True)
        old_photo = row.photo.name
        row = incoming.save()
        AdminAuditEvent.objects.create(actor=request.user, action="shop_updated",
            target_type="shop", target_id=pk,
            details={"fields": sorted(incoming.validated_data)})
        if old_photo and old_photo != row.photo.name:
            from django.core.files.storage import default_storage
            transaction.on_commit(lambda: default_storage.delete(old_photo))
    logger.info("Admin %s updated shop %s", request.user.pk, pk)
    return private(shop_data(row))


class ShopModerationInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=["suspend", "ban", "restore", "delete"])
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    suspended_until = serializers.DateTimeField(required=False)

    def validate(self, values):
        action = values["action"]
        if action != "restore" and not values.get("reason", "").strip():
            raise serializers.ValidationError({"reason": "กรุณาระบุเหตุผล"})
        if action == "suspend" and (not values.get("suspended_until") or
            values["suspended_until"] <= timezone.now()):
            raise serializers.ValidationError({"suspended_until": "ระบุวันสิ้นสุดในอนาคต"})
        return values


@api_view(["POST"])
def admin_shop_moderate(request, pk):
    require_admin(request)
    incoming = ShopModerationInput(data=request.data)
    incoming.is_valid(raise_exception=True)
    values = incoming.validated_data
    action = values["action"]
    with transaction.atomic():
        row = get_object_or_404(Shop.objects.select_for_update(), pk=pk)
        if row.moderation_status == Shop.ModerationStatus.DELETED:
            raise serializers.ValidationError("ร้านนี้ถูกลบถาวรจากแอปแล้ว")
        row.moderation_status = {
            "suspend": Shop.ModerationStatus.SUSPENDED,
            "ban": Shop.ModerationStatus.BANNED,
            "restore": Shop.ModerationStatus.ACTIVE,
            "delete": Shop.ModerationStatus.DELETED,
        }[action]
        row.suspended_until = values.get("suspended_until") if action == "suspend" else None
        row.moderation_reason = values.get("reason", "").strip()
        row.deleted_at = timezone.now() if action == "delete" else None
        row.save(update_fields=["moderation_status", "suspended_until", "moderation_reason", "deleted_at"])
        AdminAuditEvent.objects.create(actor=request.user, action=f"shop_{action}",
            target_type="shop", target_id=pk, details={
                "reason": row.moderation_reason,
                "suspended_until": row.suspended_until.isoformat() if row.suspended_until else None})
    logger.info("Admin %s moderated shop %s action=%s", request.user.pk, pk, action)
    return private(shop_data(row))


@api_view(["GET"])
def admin_mechanics(request):
    require_admin(request)
    rows = get_user_model().objects.filter(is_active=True, is_superuser=False,
        groups__name="mechanics").order_by("username", "pk")[:500]
    return private([{"id": user.pk, "username": user.username} for user in rows])


@api_view(["PATCH"])
def admin_shop(request, pk):
    require_admin(request)
    incoming = ShopMechanicsInput(data=request.data)
    incoming.is_valid(raise_exception=True)
    selected = set(incoming.validated_data["mechanic_ids"])
    with transaction.atomic():
        shop = get_object_or_404(Shop.objects.select_for_update(), pk=pk)
        if shop.moderation_status == Shop.ModerationStatus.DELETED:
            raise serializers.ValidationError("ร้านที่ลบถาวรแก้ไขช่างประจำร้านไม่ได้")
        removed = set(shop.mechanics.values_list("pk", flat=True)) - selected
        if removed and Booking.objects.filter(shop=shop, mechanic_id__in=removed,
            status__in=[Booking.Status.ACCEPTED, Booking.Status.IN_PROGRESS]).exists():
            raise serializers.ValidationError({"mechanic_ids":
                "ต้องปิดงานซ่อมที่ช่างรับไว้ก่อนถอดช่างออกจากร้าน"})
        shop.mechanics.set(sorted(selected))
        AdminAuditEvent.objects.create(actor=request.user, action="shop_mechanics_updated",
            target_type="shop", target_id=shop.pk,
            details={"mechanic_ids": sorted(selected)})
    logger.info("Admin %s updated mechanics for shop %s", request.user.pk, pk)
    return private({"id": shop.pk, "mechanic_ids": sorted(selected)})


@api_view(["GET"])
def admin_bookings(request):
    require_admin(request)
    rows = Booking.objects.select_related("customer", "shop")
    query = request.query_params.get("q", "").strip()[:100]
    if query:
        lookup = (Q(customer__username__icontains=query) |
                  Q(shop__name__icontains=query) |
                  Q(motorcycle_label__icontains=query) |
                  Q(status__icontains=query))
        if query.isdecimal():
            lookup |= Q(pk=int(query))
        rows = rows.filter(lookup)
    rows = rows.order_by("-created_at")[:100]
    return private([{"id": row.pk, "customer": row.customer.username,
                     "shop": row.shop.name if row.shop else row.shop_name,
                     "status": row.status, "motorcycle": row.motorcycle_label,
                     "appointment_at": row.appointment_at.isoformat(),
                     "archived_at": row.archived_at.isoformat() if row.archived_at else None} for row in rows])


class AdminBookingCorrectionInput(serializers.Serializer):
    appointment_at = serializers.DateTimeField(required=False)
    problem = serializers.CharField(max_length=2000, required=False, trim_whitespace=True)
    repair_notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)


@api_view(["GET", "PATCH"])
def admin_booking_detail(request, pk):
    require_admin(request)
    if request.method == "PATCH":
        with transaction.atomic():
            row = get_object_or_404(Booking.objects.select_for_update(), pk=pk)
            if row.archived_at:
                raise serializers.ValidationError("รายการที่ซ่อนแล้วแก้ไขไม่ได้")
            incoming = AdminBookingCorrectionInput(data=request.data)
            incoming.is_valid(raise_exception=True)
            values = incoming.validated_data
            if "appointment_at" in values and row.status in (
                Booking.Status.PENDING, Booking.Status.ACCEPTED
            ) and values["appointment_at"] <= timezone.now():
                raise serializers.ValidationError({"appointment_at": "ต้องเป็นเวลาในอนาคต"})
            for field, value in values.items():
                setattr(row, field, value)
            if values:
                row.save(update_fields=[*values, "updated_at"])
                AdminAuditEvent.objects.create(actor=request.user,
                    action="booking_corrected", target_type="booking", target_id=pk,
                    details={"fields": sorted(values)})
    row = get_object_or_404(Booking.objects.select_related(
        "customer", "customer__profile", "mechanic", "shop", "motorcycle"), pk=pk)
    events = row.events.select_related("actor").order_by("created_at", "pk")
    return private({
        "id": row.pk, "status": row.status,
        "customer": {"id": row.customer_id, "username": row.customer.username,
                     "name": row.customer.get_full_name(),
                     "email": row.customer.email,
                     "phone": getattr(getattr(row.customer, "profile", None), "phone", "")},
        "shop": {"id": row.shop_id, "name": row.shop.name if row.shop else row.shop_name,
                 "address": row.shop.address if row.shop else "",
                 "phone": row.shop.phone if row.shop else ""},
        "mechanic": {"id": row.mechanic_id, "username": row.mechanic.username}
                    if row.mechanic else None,
        "motorcycle": {"id": row.motorcycle_id, "brand": row.motorcycle.brand,
                       "model": row.motorcycle.model,
                       "license_plate": row.motorcycle.license_plate,
                       "year": row.motorcycle.year, "mileage": row.motorcycle.mileage},
        "motorcycle_label": row.motorcycle_label,
        "appointment_at": row.appointment_at.isoformat(),
        "problem": row.problem, "repair_notes": row.repair_notes,
        "cancellation_reason": row.cancellation_reason,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "archive_reason": row.archive_reason,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "events": [{"status": event.status, "actor": event.actor.username,
                    "created_at": event.created_at.isoformat()} for event in events],
    })


class AdminBookingActionInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=["cancel", "archive"])
    reason = serializers.CharField(max_length=1000, trim_whitespace=True)


@api_view(["POST"])
def admin_booking_action(request, pk):
    require_admin(request)
    incoming = AdminBookingActionInput(data=request.data)
    incoming.is_valid(raise_exception=True)
    action = incoming.validated_data["action"]
    reason = incoming.validated_data["reason"]
    with transaction.atomic():
        row = get_object_or_404(Booking.objects.select_for_update(), pk=pk)
        if row.archived_at:
            raise serializers.ValidationError("รายการนี้ถูกซ่อนแล้ว")
        if action == "cancel":
            if row.status not in (Booking.Status.PENDING, Booking.Status.ACCEPTED):
                raise serializers.ValidationError("ยกเลิกได้เฉพาะงานที่ยังไม่เริ่มซ่อม")
            row.status = Booking.Status.CANCELLED
            row.cancellation_reason = reason
            row.save(update_fields=["status", "cancellation_reason", "updated_at"])
            BookingEvent.objects.create(booking=row, actor=request.user, status=row.status)
            notify_booking(row, request.user)
        else:
            if row.status not in (Booking.Status.CANCELLED, Booking.Status.COMPLETED):
                raise serializers.ValidationError("ต้องปิดหรือยกเลิกงานก่อนซ่อน")
            row.archived_at = timezone.now()
            row.archive_reason = reason
            row.save(update_fields=["archived_at", "archive_reason", "updated_at"])
        AdminAuditEvent.objects.create(actor=request.user, action=f"booking_{action}",
            target_type="booking", target_id=pk, details={"reason": reason})
    return private({"id": pk, "status": row.status,
                    "archived_at": row.archived_at.isoformat() if row.archived_at else None})


@api_view(["GET", "POST"])
def admin_knowledge(request):
    require_admin(request)
    if request.method == "POST":
        incoming = KnowledgeInput(data=request.data)
        incoming.is_valid(raise_exception=True)
        row = incoming.save()
        AdminAuditEvent.objects.create(actor=request.user, action="knowledge_created",
            target_type="knowledge", target_id=row.pk)
        logger.info("Admin %s added knowledge %s", request.user.pk, row.pk)
        return private(knowledge_data(row), status=201)
    try:
        page = int(request.query_params.get("page", "1"))
    except ValueError:
        raise serializers.ValidationError({"page": "หน้าไม่ถูกต้อง"}) from None
    if page < 1 or page > 10000:
        raise serializers.ValidationError({"page": "หน้าไม่ถูกต้อง"})
    active = MotorcycleKnowledge.objects.filter(archived_at__isnull=True)
    rows = list(active[(page - 1) * 20:page * 20 + 1])
    return private({"count": active.count(), "page": page,
                    "has_more": len(rows) > 20,
                    "results": [knowledge_data(row) for row in rows[:20]]})


@api_view(["PATCH", "DELETE"])
def admin_knowledge_item(request, pk):
    require_admin(request)
    with transaction.atomic():
        row = get_object_or_404(MotorcycleKnowledge.objects.select_for_update(),
                                pk=pk, archived_at__isnull=True)
        if request.method == "DELETE":
            archive = KnowledgeArchiveInput(data=request.data)
            archive.is_valid(raise_exception=True)
            if row.embedding_status == "ready":
                try:
                    with vector_connection() as connection:
                        with connection.cursor() as cursor:
                            cursor.execute("DELETE FROM the_x_manual_vectors WHERE id = %s",
                                (uuid5(NAMESPACE_URL, f"the_x_admin_knowledge:{row.pk}"),))
                except psycopg.Error:
                    raise AdminUnavailable("ลบ embedding เดิมไม่สำเร็จ จึงยังไม่ได้ซ่อนข้อมูล") from None
            row.archived_at = timezone.now()
            row.archive_reason = archive.validated_data["reason"]
            row.embedding_status = "archived"
            row.save(update_fields=["archived_at", "archive_reason",
                                    "embedding_status", "updated_at"])
            AdminAuditEvent.objects.create(actor=request.user, action="knowledge_archived",
                target_type="knowledge", target_id=row.pk,
                details={"reason": row.archive_reason})
            return private({"id": row.pk, "archived": True})
        incoming = KnowledgeInput(row, data=request.data, partial=True)
        incoming.is_valid(raise_exception=True)
        if row.embedding_status == "ready":
            # Never leave an older vector searchable after a source or fact is edited.
            try:
                with vector_connection() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM the_x_manual_vectors WHERE id = %s",
                                       (uuid5(NAMESPACE_URL, f"the_x_admin_knowledge:{row.pk}"),))
            except psycopg.Error:
                raise AdminUnavailable("ลบ embedding เดิมไม่สำเร็จ จึงยังไม่ได้แก้ข้อมูล") from None
        row = incoming.save(embedding_status="pending", embedded_hash="", embedded_at=None)
        AdminAuditEvent.objects.create(actor=request.user, action="knowledge_updated",
            target_type="knowledge", target_id=row.pk)
    logger.info("Admin %s updated knowledge %s", request.user.pk, row.pk)
    return private(knowledge_data(row))


@api_view(["GET", "PUT"])
def admin_embedding_key(request):
    require_admin(request)
    if request.method == "GET":
        return private(credential_info())
    incoming = KeyInput(data=request.data)
    incoming.is_valid(raise_exception=True)
    key = incoming.validated_data["api_key"]
    # Only one row is used. Never log or return the plaintext or ciphertext.
    with transaction.atomic():
        row = AiEmbeddingCredential.objects.select_for_update().filter(pk=1).first()
        if row is None:
            row = AiEmbeddingCredential(pk=1)
        row.encrypted_key = credential_cipher().encrypt(key.encode()).decode()
        row.key_hint = key[-4:]
        row.save()
        AdminAuditEvent.objects.create(actor=request.user, action="embedding_key_rotated",
            target_type="embedding_key", target_id=row.pk)
    logger.info("Admin %s rotated embedding key", request.user.pk)
    return private(credential_info())


def embedding_key():
    row = AiEmbeddingCredential.objects.order_by("pk").first()
    if row is None:
        raise AdminUnavailable("กรุณาเพิ่ม Gemini Embedding API key ก่อน")
    try:
        return credential_cipher().decrypt(row.encrypted_key.encode()).decode()
    except InvalidToken:
        raise AdminUnavailable("อ่าน API key ไม่ได้ กรุณาตั้งค่าใหม่") from None


def embed_content(key, content):
    payload = {"model": EMBEDDING_MODEL, "content": {"parts": [{"text": content}]},
               "taskType": "RETRIEVAL_DOCUMENT"}
    req = Request("https://generativelanguage.googleapis.com/v1beta/" +
                  EMBEDDING_MODEL + ":embedContent",
                  data=json.dumps(payload, ensure_ascii=False).encode(), method="POST",
                  headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=25) as response:
            values = json.load(response)["embedding"]["values"]
    except HTTPError as error:
        logger.warning("Gemini embedding HTTP %s", error.code)
        raise AdminUnavailable("Gemini embedding ไม่สำเร็จ กรุณาตรวจ API key และโควตา") from None
    except (URLError, TimeoutError, KeyError, ValueError):
        raise AdminUnavailable() from None
    if len(values) != EMBEDDING_DIMENSIONS or any(
        type(value) not in (int, float) or not math.isfinite(value) for value in values
    ):
        raise AdminUnavailable("โมเดล embedding ส่งเวกเตอร์ผิดขนาด")
    return values


def vector_connection():
    password = os.getenv("AI_VECTOR_DB_PASSWORD")
    if not password:
        raise AdminUnavailable("ยังไม่ตั้งค่า AI vector database")
    try:
        return psycopg.connect(host=os.getenv("AI_VECTOR_DB_HOST", "ai-postgres"),
                               port=5432, dbname="the_x_ai_vectors", user="the_x_ai_vectors",
                               password=password, connect_timeout=5)
    except psycopg.Error:
        raise AdminUnavailable("เชื่อมต่อ AI vector database ไม่ได้") from None


@api_view(["POST"])
@throttle_classes([EmbeddingThrottle])
def admin_embed_knowledge(request, pk):
    require_admin(request)
    row = get_object_or_404(MotorcycleKnowledge, pk=pk, archived_at__isnull=True)
    if not row.reviewed:
        raise serializers.ValidationError({"reviewed": "ต้องตรวจข้อมูลและแหล่งที่มาก่อนทำ embedding"})
    year = str(row.year) if row.year else "ไม่ระบุปี"
    content = f"{row.brand} {row.model} ปี {year}\nหัวข้อ: {row.section}\n{row.content}"
    digest = hashlib.sha256((content + "\n" + row.source_url).encode()).hexdigest()
    if row.embedding_status == "ready" and row.embedded_hash == digest:
        return private(knowledge_data(row))
    vector = embed_content(embedding_key(), content)
    vector_id = uuid5(NAMESPACE_URL, f"the_x_admin_knowledge:{row.pk}")
    metadata = {"title": f"{row.brand} {row.model} ({year}) — {row.section}",
                "source_url": row.source_url, "manufacturer": row.brand,
                "model": row.model, "year": row.year, "section": row.section,
                "source_type": "admin_reviewed_motorcycle_knowledge",
                "review_level": "admin_reviewed", "embedding_model": EMBEDDING_MODEL,
                "knowledge_id": row.pk}
    with transaction.atomic():
        row = get_object_or_404(MotorcycleKnowledge.objects.select_for_update(), pk=pk)
        current_year = str(row.year) if row.year else "ไม่ระบุปี"
        current_content = f"{row.brand} {row.model} ปี {current_year}\nหัวข้อ: {row.section}\n{row.content}"
        if not row.reviewed or hashlib.sha256(
            (current_content + "\n" + row.source_url).encode()).hexdigest() != digest:
            raise KnowledgeChanged()
        try:
            with vector_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS the_x_manual_vectors
                        (id uuid PRIMARY KEY, content text, metadata jsonb, embedding vector(3072))""")
                    cursor.execute("""INSERT INTO the_x_manual_vectors (id, content, metadata, embedding)
                        VALUES (%s, %s, %s::jsonb, %s::vector)
                        ON CONFLICT (id) DO UPDATE SET content=EXCLUDED.content,
                        metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding""",
                        (vector_id, content, json.dumps(metadata, ensure_ascii=False),
                         "[" + ",".join(format(value, ".9g") for value in vector) + "]"))
        except psycopg.Error:
            logger.exception("Vector upsert failed for knowledge %s", row.pk)
            raise AdminUnavailable("บันทึก embedding ลง vector database ไม่สำเร็จ") from None
        row.embedding_status = "ready"
        row.embedded_hash = digest
        row.embedded_at = timezone.now()
        row.save(update_fields=["embedding_status", "embedded_hash", "embedded_at", "updated_at"])
        AdminAuditEvent.objects.create(actor=request.user, action="knowledge_embedded",
            target_type="knowledge", target_id=row.pk)
    logger.info("Admin %s embedded knowledge %s", request.user.pk, row.pk)
    return private(knowledge_data(row))
