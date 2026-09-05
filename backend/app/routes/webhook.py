import logging

from fastapi import APIRouter, Request

from app.avito_client import get_guest_name, parse_webhook_payload
from app.config import get_settings
from app.inbound_message import get_or_create_conversation, process_guest_message, save_conversation

log = logging.getLogger("webhook")

router = APIRouter(tags=["webhook"])


@router.post("/webhook/avito")
async def avito_webhook(request: Request):
    raw = await request.json()
    parsed = parse_webhook_payload(raw)

    chat_id = parsed.get("chat_id")
    if not chat_id:
        log.warning("Webhook без chat_id или неизвестный тип уведомления, игнорируем: %s", raw)
        return {"ok": True}

    settings = get_settings()
    author_id = parsed.get("author_id")
    own_user_id = parsed.get("own_user_id") or settings.avito_user_id
    if author_id is not None and str(author_id) == str(own_user_id):
        # Это наше же исходящее сообщение, отражённое вебхуком (например, отправленное
        # вручную администратором) — не обрабатываем повторно, иначе можно зациклиться.
        return {"ok": True}

    text = parsed.get("text") or ""
    image_url = parsed.get("image_url")

    if not text and not image_url:
        # Сообщение без текста и без фото (например, system/call/deleted) — нечего
        # передавать в Claude и нечего сохранять как реплику гостя.
        return {"ok": True}

    conversation = get_or_create_conversation(
        "avito", chat_id, parsed.get("item_id"), lambda: get_guest_name(chat_id, own_user_id)
    )
    process_guest_message("avito", conversation, text, image_url)
    save_conversation("avito", conversation)
    return {"ok": True}
