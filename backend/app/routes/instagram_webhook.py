import logging

from fastapi import APIRouter, Request, Response

from app.config import get_settings
from app.inbound_message import get_or_create_conversation, process_guest_message, save_conversation
from app.instagram_client import get_guest_name, parse_webhook_payload, verify_signature

log = logging.getLogger("instagram-webhook")

router = APIRouter(tags=["webhook"])


@router.get("/webhook/instagram")
async def verify_webhook(request: Request):
    """Meta шлёт GET при подписке вебхука, чтобы убедиться, что мы владеем
    этим URL — нужно вернуть hub.challenge, если verify_token совпадает."""
    params = request.query_params
    settings = get_settings()
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.instagram_webhook_verify_token
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    return Response(status_code=403)


@router.post("/webhook/instagram")
async def instagram_webhook(request: Request):
    body = await request.body()
    if not verify_signature(body, request.headers.get("X-Hub-Signature-256")):
        log.warning("Instagram webhook: неверная подпись, игнорируем")
        return Response(status_code=403)

    raw = await request.json()
    parsed = parse_webhook_payload(raw)
    if not parsed or not parsed.get("chat_id"):
        return {"ok": True}

    chat_id = parsed["chat_id"]
    text = parsed.get("text") or ""
    image_url = parsed.get("image_url")

    conversation = get_or_create_conversation(
        "instagram", chat_id, None, lambda: get_guest_name(chat_id)
    )
    process_guest_message("instagram", conversation, text, image_url)
    save_conversation("instagram", conversation)
    return {"ok": True}
