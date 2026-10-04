"""Bounded, redacted database inspection for the in-app administrator.

This deliberately does not execute client SQL or mutate auth, OIDC or audit
tables. Domain writes go through their validated APIs and lifecycle rules.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.apps import apps
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from oidc_provider.models import Token
from rest_framework import serializers
from rest_framework.decorators import api_view

from .admin_api import private, require_admin
from .models import (AdminAuditEvent, AiConversation, KnowledgeChunk,
                     Notification, ShopConversation, ShopMessage)


SENSITIVE_PARTS = (
    "password", "secret", "token", "key", "session_data", "cipher",
    "private", "salt", "authorization", "nonce", "verifier", "signature",
    "credential", "api_key", "auth_code", "request_id", "code",
)
ACTION_TABLES = {
    "auth_user": "users",
    "garage_shop": "shops",
    "garage_motorcycle": "motorcycles",
    "garage_booking": "bookings",
    "garage_motorcycleknowledge": "knowledge",
    "garage_shopconversation": "conversation",
    "garage_shopmessage": "message",
    "garage_aiconversation": "ai_conversation",
    "garage_notification": "notification",
    "garage_knowledgechunk": "knowledge_chunk",
    "oidc_provider_token": "oidc_token",
}


def sensitive(name):
    lowered = name.lower()
    return any(part in lowered for part in SENSITIVE_PARTS)


def safe_value(name, value):
    if sensitive(name) or isinstance(value, (bytes, memoryview)):
        return "[redacted]" if value is not None else None
    if isinstance(value, dict):
        return {str(key)[:80]: safe_value(str(key), item)
                for key, item in list(value.items())[:50]}
    if isinstance(value, (list, tuple)):
        return [safe_value(name, item) for item in value[:50]]
    if isinstance(value, (datetime, date, Decimal, UUID)):
        return str(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:2000] + ("…" if len(value) > 2000 else "")
    try:
        return safe_value(name, json.loads(json.dumps(value, default=str)))
    except (TypeError, ValueError):
        return str(value)[:2000]


def known_models():
    return {model._meta.db_table: model._meta.label for model in
            apps.get_models(include_auto_created=True) if not model._meta.proxy}


@api_view(["GET"])
def admin_database_tables(request):
    require_admin(request)
    labels = known_models()
    tables = connection.introspection.table_names()
    return private([{"table": table, "model": labels.get(table),
                     "actions": ACTION_TABLES.get(table)} for table in sorted(tables)])


@api_view(["GET"])
def admin_database_rows(request, table):
    require_admin(request)
    if table not in connection.introspection.table_names():
        raise serializers.ValidationError({"table": "ไม่พบตารางนี้"})
    try:
        page = int(request.query_params.get("page", "1"))
    except ValueError as error:
        raise serializers.ValidationError({"page": "หน้าไม่ถูกต้อง"}) from error
    if page < 1 or page > 10000:
        raise serializers.ValidationError({"page": "หน้าไม่ถูกต้อง"})
    page_size = 30
    offset = (page - 1) * page_size
    quoted = connection.ops.quote_name(table)
    # Table names come solely from Django's database introspection, never raw
    # client input. Values remain bound parameters.
    with connection.cursor() as cursor:
        columns = [column.name for column in connection.introspection.get_table_description(cursor, table)]
        order = f" ORDER BY {connection.ops.quote_name('id')} DESC" if "id" in columns else ""
        cursor.execute(f"SELECT * FROM {quoted}{order} LIMIT %s OFFSET %s",
                       [page_size + 1, offset])
        names = [column[0] for column in cursor.description]
        records = cursor.fetchall()
    return private({
        "table": table, "model": known_models().get(table),
        "actions": ACTION_TABLES.get(table),
        "columns": names, "page": page,
        "has_more": len(records) > page_size,
        "rows": [{name: safe_value(name, value) for name, value in zip(names, record)}
                 for record in records[:page_size]],
    })


class RowActionInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=["archive", "restore", "redact",
                                              "hide", "enable", "disable", "revoke"])
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)

    def validate(self, values):
        if values["action"] in ("archive", "redact", "hide", "disable", "revoke") and not values.get("reason", "").strip():
            raise serializers.ValidationError({"reason": "กรุณาระบุเหตุผล"})
        return values


class AiConversationEditInput(serializers.Serializer):
    title = serializers.CharField(max_length=80, trim_whitespace=True)


class KnowledgeChunkEditInput(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    source_url = serializers.URLField(max_length=1000, required=False)
    locator = serializers.CharField(max_length=120, required=False, allow_blank=True)
    content = serializers.CharField(max_length=1800, required=False)
    keywords = serializers.ListField(child=serializers.CharField(min_length=2,
        max_length=100), min_length=1, max_length=30, required=False)


@api_view(["PATCH"])
def admin_database_edit(request, table, pk):
    require_admin(request)
    models = {"garage_aiconversation": (AiConversation, AiConversationEditInput),
              "garage_knowledgechunk": (KnowledgeChunk, KnowledgeChunkEditInput)}
    if table not in models:
        raise serializers.ValidationError({"table": "ตารางนี้แก้ไขผ่านแอปไม่ได้"})
    model, form = models[table]
    try:
        record_pk = model._meta.pk.to_python(pk)
    except (ValueError, DjangoValidationError) as error:
        raise serializers.ValidationError({"id": "รหัสรายการไม่ถูกต้อง"}) from error
    incoming = form(data=request.data)
    incoming.is_valid(raise_exception=True)
    values = incoming.validated_data
    if not values:
        raise serializers.ValidationError("ไม่มีข้อมูลให้แก้ไข")
    with transaction.atomic():
        row = get_object_or_404(model.objects.select_for_update(), pk=record_pk)
        for field, value in values.items():
            setattr(row, field, value)
        if model is KnowledgeChunk:
            row.is_active = False  # Revised source must be reviewed again.
            try:
                row.full_clean()
            except DjangoValidationError as error:
                raise serializers.ValidationError(error.message_dict) from error
            row.save(update_fields=[*values, "is_active", "updated_at"])
        else:
            row.save(update_fields=list(values))
        AdminAuditEvent.objects.create(actor=request.user,
            action="database_record_edited", target_type=table,
            target_id=record_pk if isinstance(record_pk, int) else None,
            details={"record_id": str(record_pk), "fields": sorted(values)})
    return private({"table": table, "id": str(record_pk), "fields": sorted(values)})


@api_view(["POST"])
def admin_database_action(request, table, pk):
    require_admin(request)
    incoming = RowActionInput(data=request.data)
    incoming.is_valid(raise_exception=True)
    action = incoming.validated_data["action"]
    reason = incoming.validated_data.get("reason", "").strip()
    allowed = {
        "garage_shopconversation": (ShopConversation, {"archive", "restore"}),
        "garage_shopmessage": (ShopMessage, {"redact"}),
        "garage_aiconversation": (AiConversation, {"archive", "restore"}),
        "garage_notification": (Notification, {"hide", "restore"}),
        "garage_knowledgechunk": (KnowledgeChunk, {"disable", "enable"}),
        "oidc_provider_token": (Token, {"revoke"}),
    }
    if table not in allowed or action not in allowed[table][1]:
        raise serializers.ValidationError({"action": "ตารางหรือคำสั่งนี้แก้ไขผ่านแอปไม่ได้"})
    model = allowed[table][0]
    try:
        record_pk = model._meta.pk.to_python(pk)
    except (ValueError, DjangoValidationError) as error:
        raise serializers.ValidationError({"id": "รหัสรายการไม่ถูกต้อง"}) from error
    with transaction.atomic():
        row = get_object_or_404(model.objects.select_for_update(), pk=record_pk)
        if model in (ShopConversation, AiConversation):
            row.archived_at = timezone.now() if action == "archive" else None
            row.archive_reason = reason if action == "archive" else ""
            row.save(update_fields=["archived_at", "archive_reason"])
        elif model is ShopMessage:
            if row.redacted_at:
                raise serializers.ValidationError("ข้อความนี้ถูกซ่อนแล้ว")
            row.redacted_at = timezone.now()
            row.redaction_reason = reason
            row.save(update_fields=["redacted_at", "redaction_reason"])
        elif model is Notification:
            row.hidden_at = timezone.now() if action == "hide" else None
            row.save(update_fields=["hidden_at"])
        elif model is KnowledgeChunk:
            row.is_active = action == "enable"
            row.save(update_fields=["is_active", "updated_at"])
        elif model is Token:
            row.delete()  # A token is an ephemeral credential, not domain history.
        AdminAuditEvent.objects.create(actor=request.user,
            action=f"{ACTION_TABLES[table]}_{action}", target_type=table,
            target_id=record_pk if isinstance(record_pk, int) else None,
            details={"reason": reason, "record_id": str(record_pk)})
    return private({"table": table, "id": str(record_pk), "action": action})
