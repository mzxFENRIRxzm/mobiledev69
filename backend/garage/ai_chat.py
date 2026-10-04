"""Authenticated AI chat; n8n receives no account identifiers or OIDC tokens."""
import json
import logging
import time
from datetime import timedelta
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import APIException, Throttled
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from .models import AiConversation, AiTurn, KnowledgeChunk

logger = logging.getLogger(__name__)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


urlopen = build_opener(NoRedirect).open


class AssistantUnavailable(APIException):
    status_code = 503
    default_detail = "แชต AI ยังไม่พร้อมใช้งาน กรุณาลองใหม่ภายหลัง"


class ChatBusy(APIException):
    status_code = 409
    default_detail = "ห้องนี้กำลังรับคำตอบ กรุณารอสักครู่แล้วโหลดใหม่"


class PromptSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=1000, allow_blank=False, trim_whitespace=True)
    conversation_id = serializers.UUIDField(required=False)
    request_id = serializers.UUIDField(required=False, default=uuid4)


class AiChatThrottle(UserRateThrottle):
    rate = "10/min"


def private_response(data, **kwargs):
    response = Response(data, **kwargs)
    response["Cache-Control"] = "no-store"
    return response


def turn_data(turn):
    return {"id": turn.pk, "request_id": str(turn.request_id), "message": turn.message,
            "reply": turn.reply, "status": turn.status, "sources": turn.sources,
            "error_code": turn.error_code, "created_at": turn.created_at.isoformat()}


def result_data(turn):
    return {**turn_data(turn), "conversation_id": str(turn.conversation_id)}


@api_view(["GET", "POST"])
def ai_conversations(request):
    if request.method == "POST":
        room = AiConversation.objects.create(owner=request.user)
        return private_response({"id": str(room.pk), "title": room.title}, status=201)
    rooms = AiConversation.objects.filter(owner=request.user, archived_at__isnull=True)[:50]
    return private_response([{"id": str(r.pk), "title": r.title} for r in rooms])


@api_view(["GET"])
def ai_conversation(request, pk):
    room = get_object_or_404(AiConversation, pk=pk, owner=request.user,
                             archived_at__isnull=True)
    room.turns.filter(status="pending", updated_at__lt=timezone.now()-timedelta(seconds=60)).update(
        status="failed", error_code="timeout", updated_at=timezone.now())
    from .history import history_page
    page = history_page(room.turns, request, lambda rows: [turn_data(t) for t in rows], size=50)
    return private_response({"id": str(room.pk), "title": room.title,
                             "turns": page if isinstance(page, list) else page['results'],
                             **({} if isinstance(page, list) else {'has_more': page['has_more'], 'cursor': page['cursor']})})


def retrieve(message):
    """MVP retrieval of reviewed keyword aliases (including Thai phrases).
    Bounded to 500 chunks; no claim of semantic/vector search.
    """
    query = message.casefold()
    matches = []
    for chunk in KnowledgeChunk.objects.filter(is_active=True).order_by("pk")[:500]:
        score = sum(len(word) for word in chunk.keywords
                    if isinstance(word, str) and len(word.strip()) >= 2 and word.casefold() in query)
        if score:
            matches.append((score, chunk))
    matches.sort(key=lambda pair: (-pair[0], pair[1].pk))
    return [{"id": c.pk, "title": c.title, "url": c.source_url, "locator": c.locator,
             "excerpt": c.content[:1800]} for _, c in matches[:3]]


def check_config():
    url = urlparse(settings.AI_CHAT_WEBHOOK_URL)
    internal = settings.AI_CHAT_INTERNAL_N8N and url.scheme == "http" and url.netloc == "n8n:5678"
    if not url.hostname or url.username or url.password or url.query or url.fragment:
        raise AssistantUnavailable("ยังไม่ได้ตั้งค่าบริการแชต AI ให้ถูกต้อง")
    if url.scheme != "https" and not internal:
        raise AssistantUnavailable("AI webhook ต้องใช้ HTTPS หรือ n8n ในเครือข่าย Docker ที่กำหนด")
    if not settings.AI_CHAT_WEBHOOK_TOKEN:
        raise AssistantUnavailable("ยังไม่ได้ตั้งค่าการยืนยันตัวตนของ AI webhook")


def call_assistant(payload):
    req = Request(settings.AI_CHAT_WEBHOOK_URL, data=json.dumps(payload).encode(), method="POST",
                  headers={"Content-Type": "application/json",
                           "Authorization": f"Bearer {settings.AI_CHAT_WEBHOOK_TOKEN}"})
    try:
        with urlopen(req, timeout=25) as response:
            raw = response.read(32769)
            if len(raw) > 32768:
                raise ValueError("oversized response")
            result = json.loads(raw)
        if isinstance(result, dict) and result.get("error") == "rate_limited":
            raise Throttled(wait=60, detail="AI ใช้โควตาครบแล้ว กรุณารอแล้วลองใหม่")
        if not isinstance(result, dict) or not isinstance(result.get("reply"), str) or not result["reply"].strip():
            raise ValueError("invalid response")
        if len(result["reply"]) > 6000:
            raise ValueError("reply too long")
        citations = result.get("citation_ids", [])
        if not isinstance(citations, list) or any(type(x) is not int for x in citations):
            raise ValueError("invalid citations")
        return result
    except HTTPError as error:
        if error.code == 429:
            raise Throttled(wait=60, detail="AI ใช้โควตาครบแล้ว กรุณารอแล้วลองใหม่") from None
        logger.warning("AI upstream HTTP failure: %s", error.code)
        raise AssistantUnavailable from None
    except (URLError, TimeoutError, ValueError, OSError):
        logger.warning("AI upstream request failed")
        raise AssistantUnavailable from None


@api_view(["POST"])
@throttle_classes([AiChatThrottle])
def ai_chat(request):
    data = PromptSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    values = data.validated_data
    check_config()
    with transaction.atomic():
        if values.get("conversation_id"):
            room = get_object_or_404(AiConversation.objects.select_for_update(),
                                     pk=values["conversation_id"], owner=request.user,
                                     archived_at__isnull=True)
        else:
            room = AiConversation.objects.create(owner=request.user, title=values["message"][:80])
        room.turns.filter(status="pending", updated_at__lt=timezone.now()-timedelta(seconds=60)).update(
            status="failed", error_code="timeout", updated_at=timezone.now())
        turn = room.turns.filter(request_id=values["request_id"]).first()
        if turn and turn.message != values["message"]:
            raise serializers.ValidationError("request_id นี้ถูกใช้กับข้อความอื่นแล้ว")
        if turn and turn.status == "completed":
            return private_response(result_data(turn))
        if room.turns.filter(status="pending").exists():
            raise ChatBusy()
        if turn:
            turn.status, turn.error_code = "pending", ""
            turn.save(update_fields=["status", "error_code", "updated_at"])
        else:
            turn = AiTurn.objects.create(conversation=room, message=values["message"], request_id=values["request_id"])
        if room.title == "บทสนทนาใหม่":
            room.title = values["message"][:80]
            room.save(update_fields=["title"])
        attempt_started = turn.updated_at
        history = list(room.turns.filter(status="completed", pk__lt=turn.pk).order_by("-pk")[:4])
    started = time.monotonic()
    try:
        sources = retrieve(turn.message)
        result = call_assistant({"message": turn.message,
            "conversation_id": str(room.pk),
            "history": [{"message": t.message, "reply": t.reply[:1500]} for t in reversed(history)],
            "sources": sources})
        cited = [{k: v for k, v in s.items() if k != "excerpt"} for s in sources
                 if s["id"] in result.get("citation_ids", [])]
        updated = AiTurn.objects.filter(pk=turn.pk, status="pending", updated_at=attempt_started).update(
            reply=result["reply"].strip(), sources=cited, status="completed", error_code="",
            latency_ms=int((time.monotonic()-started)*1000), updated_at=timezone.now())
        if not updated:
            raise ChatBusy()
    except Exception as error:
        AiTurn.objects.filter(pk=turn.pk, status="pending", updated_at=attempt_started).update(
            status="failed", error_code="rate_limited" if isinstance(error, Throttled) else "unavailable",
            latency_ms=int((time.monotonic()-started)*1000), updated_at=timezone.now())
        raise
    turn.refresh_from_db()
    return private_response(result_data(turn))
