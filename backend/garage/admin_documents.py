"""Admin-only upload, review, and vector publishing of document excerpts."""

import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

import psycopg
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes

from .admin_api import (AdminUnavailable, EMBEDDING_MODEL, EmbeddingThrottle,
                        embed_content, embedding_key, private, require_admin,
                        vector_connection)
from .knowledge_files import KnowledgeFileError, extract_file
from .models import AdminAuditEvent, KnowledgeDocument


def _vector_id(document_id, index):
    return uuid5(NAMESPACE_URL, f"the_x_document:{document_id}:{index}")


def _summary(row):
    sections = row.sections
    return {"id": row.pk, "title": row.title, "filename": row.filename,
            "file_type": row.file_type, "file_size": row.file_size,
            "sha256": row.sha256, "brand": row.brand, "model": row.model,
            "year": row.year, "source_url": row.source_url,
            "section_count": len(sections),
            "reviewed_count": sum(section["reviewed"] for section in sections),
            "embedded_count": sum(section["embedding_status"] == "ready" for section in sections),
            "created_at": row.created_at.isoformat()}


class UploadInput(serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(max_length=200)
    source_url = serializers.URLField(max_length=1000, required=False, allow_blank=True)
    brand = serializers.CharField(max_length=100, required=False, allow_blank=True)
    model = serializers.CharField(max_length=160, required=False, allow_blank=True)
    year = serializers.IntegerField(min_value=1900, max_value=2100, required=False,
                                    allow_null=True)

    def validate_source_url(self, value):
        if value and not value.startswith("https://"):
            raise serializers.ValidationError("URL แหล่งข้อมูลต้องใช้ HTTPS")
        return value


class SectionInput(serializers.Serializer):
    content = serializers.CharField(max_length=1400, required=False)
    reviewed = serializers.BooleanField(required=False)


def _remove_vector(row, index):
    if row.sections[index]["embedding_status"] != "ready":
        return
    try:
        with vector_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM the_x_manual_vectors WHERE id = %s",
                               (_vector_id(row.pk, index),))
    except psycopg.Error:
        raise AdminUnavailable("นำ embedding เดิมออกไม่ได้ กรุณาลองอีกครั้ง") from None


@api_view(["GET", "POST"])
def admin_documents(request):
    require_admin(request)
    if request.method == "POST":
        incoming = UploadInput(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = incoming.validated_data
        try:
            extracted = extract_file(values["file"])
        except KnowledgeFileError as error:
            raise serializers.ValidationError({"file": str(error)}) from None
        row = KnowledgeDocument.objects.create(
            **extracted, title=values["title"], source_url=values.get("source_url", ""),
            brand=values.get("brand", ""), model=values.get("model", ""),
            year=values.get("year"))
        AdminAuditEvent.objects.create(actor=request.user, action="document_uploaded",
            target_type="knowledge_document", target_id=row.pk,
            details={"filename": row.filename, "sha256": row.sha256,
                     "sections": len(row.sections)})
        return private(_summary(row), status=201)
    try:
        page = int(request.query_params.get("page", "1"))
    except ValueError:
        raise serializers.ValidationError({"page": "หน้าไม่ถูกต้อง"}) from None
    if not 1 <= page <= 10000:
        raise serializers.ValidationError({"page": "หน้าไม่ถูกต้อง"})
    queryset = KnowledgeDocument.objects.filter(archived_at__isnull=True)
    rows = list(queryset[(page - 1) * 20:page * 20 + 1])
    return private({"count": queryset.count(), "page": page, "has_more": len(rows) > 20,
                    "results": [_summary(row) for row in rows[:20]]})


@api_view(["GET", "DELETE"])
def admin_document(request, pk):
    require_admin(request)
    if request.method == "GET":
        row = get_object_or_404(KnowledgeDocument, pk=pk, archived_at__isnull=True)
        return private({**_summary(row), "extracted_text": row.extracted_text,
                        "sections": row.sections})
    with transaction.atomic():
        row = get_object_or_404(KnowledgeDocument.objects.select_for_update(),
                                pk=pk, archived_at__isnull=True)
        ready = [index for index, section in enumerate(row.sections)
                 if section["embedding_status"] == "ready"]
        if ready:
            try:
                with vector_connection() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("DELETE FROM the_x_manual_vectors WHERE id = ANY(%s::uuid[])",
                                       ([str(_vector_id(pk, index)) for index in ready],))
            except psycopg.Error:
                raise AdminUnavailable("นำ embedding ออกไม่ได้ จึงยังไม่ซ่อนเอกสาร") from None
        row.archived_at = timezone.now()
        row.save(update_fields=["archived_at", "updated_at"])
        AdminAuditEvent.objects.create(actor=request.user, action="document_archived",
            target_type="knowledge_document", target_id=pk)
    return private({"id": pk, "archived": True})


@api_view(["PATCH"])
def admin_document_section(request, pk, index):
    require_admin(request)
    incoming = SectionInput(data=request.data)
    incoming.is_valid(raise_exception=True)
    if not incoming.validated_data:
        raise serializers.ValidationError("ไม่มีข้อมูลที่แก้ไข")
    with transaction.atomic():
        row = get_object_or_404(KnowledgeDocument.objects.select_for_update(),
                                pk=pk, archived_at__isnull=True)
        if index >= len(row.sections):
            raise serializers.ValidationError("ไม่พบช่วงข้อความ")
        sections = list(row.sections)
        section = dict(sections[index])
        changed = "content" in incoming.validated_data and \
            incoming.validated_data["content"].strip() != section["content"]
        if changed and incoming.validated_data.get("reviewed") is True:
            raise serializers.ValidationError("แก้ข้อความแล้วต้องตรวจอีกครั้งในคำขอถัดไป")
        unreviewed = incoming.validated_data.get("reviewed") is False
        if changed or unreviewed:
            _remove_vector(row, index)
            section["embedding_status"] = "pending"
            section["embedded_hash"] = ""
            section["reviewed"] = False
        if changed:
            section["content"] = incoming.validated_data["content"].strip()
        if "reviewed" in incoming.validated_data:
            section["reviewed"] = incoming.validated_data["reviewed"]
        sections[index] = section
        row.sections = sections
        row.save(update_fields=["sections", "updated_at"])
        AdminAuditEvent.objects.create(actor=request.user, action="document_section_updated",
            target_type="knowledge_document", target_id=pk, details={"index": index})
    return private({"index": index, **section})


@api_view(["POST"])
@throttle_classes([EmbeddingThrottle])
def admin_embed_document_section(request, pk, index):
    require_admin(request)
    row = get_object_or_404(KnowledgeDocument, pk=pk, archived_at__isnull=True)
    if index >= len(row.sections):
        raise serializers.ValidationError("ไม่พบช่วงข้อความ")
    section = row.sections[index]
    if not section["reviewed"]:
        raise serializers.ValidationError("ต้องตรวจช่วงข้อความและสิทธิ์ใช้ข้อมูลก่อน")
    header = f"{row.brand} {row.model} ปี {row.year or 'ไม่ระบุ'}\n{row.title}\n{section['locator']}"
    text = f"{header}\n{section['content']}"
    digest = hashlib.sha256((text + row.source_url).encode()).hexdigest()
    if section["embedding_status"] == "ready" and section["embedded_hash"] == digest:
        return private({"index": index, **section})
    vector = embed_content(embedding_key(), text)
    with transaction.atomic():
        row = get_object_or_404(KnowledgeDocument.objects.select_for_update(),
                                pk=pk, archived_at__isnull=True)
        current = row.sections[index]
        current_text = f"{row.brand} {row.model} ปี {row.year or 'ไม่ระบุ'}\n{row.title}\n{current['locator']}\n{current['content']}"
        if not current["reviewed"] or hashlib.sha256(
            (current_text + row.source_url).encode()).hexdigest() != digest:
            raise serializers.ValidationError("ข้อมูลเปลี่ยนระหว่างทำ embedding กรุณาลองใหม่")
        metadata = {"title": row.title, "source_url": row.source_url,
                    "source_type": "admin_uploaded_document", "document_id": row.pk,
                    "filename": row.filename, "sha256": row.sha256,
                    "manufacturer": row.brand, "model": row.model, "year": row.year,
                    "section": current["locator"], "review_level": "admin_reviewed",
                    "embedding_model": EMBEDDING_MODEL}
        try:
            with vector_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""CREATE TABLE IF NOT EXISTS the_x_manual_vectors
                        (id uuid PRIMARY KEY, content text, metadata jsonb, embedding vector(3072))""")
                    cursor.execute("""INSERT INTO the_x_manual_vectors (id, content, metadata, embedding)
                        VALUES (%s, %s, %s::jsonb, %s::vector)
                        ON CONFLICT (id) DO UPDATE SET content=EXCLUDED.content,
                        metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding""",
                        (_vector_id(pk, index), text, json.dumps(metadata),
                         "[" + ",".join(str(value) for value in vector) + "]"))
        except psycopg.Error:
            raise AdminUnavailable("บันทึก embedding ไม่สำเร็จ") from None
        sections = list(row.sections)
        sections[index] = {**current, "embedding_status": "ready", "embedded_hash": digest}
        row.sections = sections
        row.save(update_fields=["sections", "updated_at"])
        AdminAuditEvent.objects.create(actor=request.user, action="document_section_embedded",
            target_type="knowledge_document", target_id=pk, details={"index": index})
    return private({"index": index, **sections[index]})
