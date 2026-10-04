"""Admin view of the PGVector passages that the n8n RAG tool actually searches."""

import json
import logging
import psycopg
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import NotFound

from .admin_api import (AdminUnavailable, EmbeddingThrottle, embed_content,
                        embedding_key, private, require_admin, vector_connection)
from .models import AdminAuditEvent

logger = logging.getLogger(__name__)
TABLE = "the_x_manual_vectors"


class VectorEditInput(serializers.Serializer):
    content = serializers.CharField(max_length=3000, trim_whitespace=True, required=False)
    title = serializers.CharField(max_length=250, trim_whitespace=True, required=False)
    model = serializers.CharField(max_length=160, trim_whitespace=True, required=False)
    year = serializers.IntegerField(min_value=1900, max_value=2100, allow_null=True,
                                    required=False)
    section = serializers.CharField(max_length=120, trim_whitespace=True, required=False)
    source_url = serializers.URLField(max_length=1000, required=False)

    def validate_source_url(self, value):
        if not value.startswith("https://"):
            raise serializers.ValidationError("แหล่งข้อมูลต้องใช้ HTTPS")
        return value


class VectorDeleteInput(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=500, trim_whitespace=True)


def passage(row):
    identifier, content, metadata = row
    metadata = metadata if isinstance(metadata, dict) else json.loads(metadata)
    return {"id": str(identifier), "content": content, "metadata": metadata}


def ensure_archive(cursor):
    # This table is intentionally outside the retrieval table. Old vectors remain
    # available to administrators for audit but cannot be returned by the RAG tool.
    cursor.execute("""CREATE TABLE IF NOT EXISTS the_x_manual_vector_history (
        revision_id bigserial PRIMARY KEY, id uuid NOT NULL, content text NOT NULL,
        metadata jsonb NOT NULL, embedding vector(3072) NOT NULL,
        action text NOT NULL, reason text NOT NULL, actor_id bigint NOT NULL,
        archived_at timestamptz NOT NULL DEFAULT now())""")


def archive(cursor, pk, action, reason, actor_id):
    ensure_archive(cursor)
    cursor.execute("""INSERT INTO the_x_manual_vector_history
        (id, content, metadata, embedding, action, reason, actor_id)
        SELECT id, content, metadata, embedding, %s, %s, %s
        FROM the_x_manual_vectors WHERE id = %s""",
        (action, reason, actor_id, pk))


@api_view(["GET"])
def admin_vectors(request):
    require_admin(request)
    try:
        page = int(request.query_params.get("page", "1"))
    except ValueError:
        raise serializers.ValidationError({"page": "หน้าไม่ถูกต้อง"}) from None
    if page < 1 or page > 10000:
        raise serializers.ValidationError({"page": "หน้าไม่ถูกต้อง"})
    query = request.query_params.get("q", "").strip()[:100]
    pattern = f"%{query}%"
    try:
        with vector_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""SELECT count(*) FROM the_x_manual_vectors
                    WHERE (%s = '' OR metadata->>'model' ILIKE %s OR
                           metadata->>'title' ILIKE %s OR content ILIKE %s)""",
                    (query, pattern, pattern, pattern))
                total = cursor.fetchone()[0]
                cursor.execute("""SELECT id, content, metadata FROM the_x_manual_vectors
                    WHERE (%s = '' OR metadata->>'model' ILIKE %s OR
                           metadata->>'title' ILIKE %s OR content ILIKE %s)
                    ORDER BY metadata->>'model' ASC, metadata->>'section' ASC, id ASC
                    LIMIT 21 OFFSET %s""",
                    (query, pattern, pattern, pattern, (page - 1) * 20))
                rows = cursor.fetchall()
    except psycopg.Error:
        logger.exception("Could not list AI vector passages")
        raise AdminUnavailable("อ่านฐานความรู้ AI ไม่สำเร็จ") from None
    return private({"count": total, "page": page, "has_more": len(rows) > 20,
                    "results": [passage(row) for row in rows[:20]]})


@api_view(["PATCH", "DELETE"])
@throttle_classes([EmbeddingThrottle])
def admin_vector_item(request, pk):
    require_admin(request)
    if request.method == "DELETE":
        incoming = VectorDeleteInput(data=request.data)
    else:
        incoming = VectorEditInput(data=request.data)
    incoming.is_valid(raise_exception=True)
    changes = incoming.validated_data
    if request.method == "PATCH" and not changes:
        raise serializers.ValidationError("ไม่มีข้อมูลให้แก้ไข")
    try:
        with vector_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, content, metadata FROM the_x_manual_vectors WHERE id = %s FOR UPDATE",
                               (pk,))
                row = cursor.fetchone()
                if row is None:
                    raise NotFound("ไม่พบข้อมูล AI นี้")
                old = passage(row)
                if old["metadata"].get("knowledge_id") is not None:
                    raise serializers.ValidationError(
                        "รายการนี้สร้างจากข้อมูลที่ Admin เพิ่มเอง กรุณาจัดการในส่วนด้านล่าง")
                if request.method == "DELETE":
                    archive(cursor, pk, "deleted", changes["reason"], request.user.pk)
                    cursor.execute("DELETE FROM the_x_manual_vectors WHERE id = %s", (pk,))
                    result = {"id": str(pk), "deleted": True}
                    action = "vector_deleted"
                    details = {"reason": changes["reason"]}
                else:
                    content = changes.get("content", old["content"])
                    metadata = dict(old["metadata"])
                    for name in ("title", "model", "year", "section", "source_url"):
                        if name in changes:
                            metadata[name] = changes[name]
                    metadata["review_level"] = "admin_reviewed"
                    metadata["admin_edited_at"] = timezone.now().isoformat()
                    metadata["admin_edited_by"] = request.user.pk
                    if content != old["content"]:
                        # Never serve revised text with the previous passage's vector.
                        vector = embed_content(embedding_key(), content)
                        vector_text = "[" + ",".join(format(value, ".9g") for value in vector) + "]"
                        archive(cursor, pk, "edited", "content re-embedded", request.user.pk)
                        cursor.execute("""UPDATE the_x_manual_vectors SET content = %s,
                            metadata = %s::jsonb, embedding = %s::vector WHERE id = %s""",
                            (content, json.dumps(metadata, ensure_ascii=False), vector_text, pk))
                    else:
                        archive(cursor, pk, "edited", "metadata corrected", request.user.pk)
                        cursor.execute("""UPDATE the_x_manual_vectors SET metadata = %s::jsonb
                            WHERE id = %s""", (json.dumps(metadata, ensure_ascii=False), pk))
                    result = {"id": str(pk), "content": content, "metadata": metadata}
                    action = "vector_updated"
                    details = {"fields": sorted(changes)}
        AdminAuditEvent.objects.create(actor=request.user, action=action,
            target_type="ai_vector", details={"vector_id": str(pk), **details})
    except psycopg.Error:
        logger.exception("Could not change AI vector passage %s", pk)
        raise AdminUnavailable("แก้ไขฐานความรู้ AI ไม่สำเร็จ") from None
    return private(result)
