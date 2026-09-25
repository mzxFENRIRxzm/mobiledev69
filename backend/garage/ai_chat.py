import json
import logging
from urllib.parse import urlparse
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle


logger = logging.getLogger(__name__)


class AssistantUnavailable(APIException):
    status_code = 503
    default_detail = "แชต AI ยังไม่พร้อมใช้งาน กรุณาลองใหม่ภายหลัง"


class PromptSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=1000, allow_blank=False, trim_whitespace=True)


class AiChatThrottle(UserRateThrottle):
    rate = "10/min"


@api_view(["POST"])
@throttle_classes([AiChatThrottle])
def ai_chat(request):
    data = PromptSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    if not settings.AI_CHAT_WEBHOOK_URL:
        raise AssistantUnavailable("ยังไม่ได้ตั้งค่าบริการแชต AI")
    if urlparse(settings.AI_CHAT_WEBHOOK_URL).scheme != "https":
        raise AssistantUnavailable("AI webhook ต้องใช้ HTTPS")
    payload = json.dumps({"message": data.validated_data["message"]}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if settings.AI_CHAT_WEBHOOK_TOKEN:
        headers["Authorization"] = f"Bearer {settings.AI_CHAT_WEBHOOK_TOKEN}"
    upstream = Request(settings.AI_CHAT_WEBHOOK_URL, data=payload, headers=headers, method="POST")
    try:
        with urlopen(upstream, timeout=15) as response:
            result = json.loads(response.read(16_385))
    except (URLError, TimeoutError, ValueError, OSError):
        logger.exception("AI chat webhook failed")
        raise AssistantUnavailable
    if not isinstance(result, dict) or not isinstance(result.get("reply"), str) or not result["reply"].strip():
        raise AssistantUnavailable
    return Response({"reply": result["reply"][:4000]})
