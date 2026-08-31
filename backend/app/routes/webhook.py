import datetime as dt
import logging

from fastapi import APIRouter, Request

from app.avito_client import get_guest_name, parse_webhook_payload, send_message
from app.claude_agent import generate_reply
from app.config import get_settings
from app.firestore_db import CONVERSATIONS_COLLECTION, get_db
from app.models import Conversation, Message
from app.scenario_engine import continue_scenario, find_matching_scenario, start_scenario
from app.telegram_notify import notify_admin

log = logging.getLogger("webhook")

router = APIRouter(tags=["webhook"])


def _get_or_create_conversation(chat_id: str, item_id: str | None, own_user_id: str) -> Conversation:
    db = get_db()
    ref = db.collection(CONVERSATIONS_COLLECTION).document(chat_id)
    doc = ref.get()
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    if doc.exists:
        return Conversation(id=doc.id, **doc.to_dict())

    # Вебхук не содержит имени отправителя — запрашиваем его только один раз,
    # при первом сообщении в новом чате.
    guest_name = get_guest_name(chat_id, own_user_id)

    conversation = Conversation(
        conversationId=chat_id,
        guestName=guest_name,
        chatId=chat_id,
        itemId=item_id,
        messages=[],
        status="open",
        createdAt=now,
        updatedAt=now,
    )
    ref.set(conversation.model_dump(exclude={"id"}))
    return conversation


def _save_conversation(conversation: Conversation) -> None:
    db = get_db()
    conversation.updatedAt = dt.datetime.now(dt.timezone.utc).isoformat()
    db.collection(CONVERSATIONS_COLLECTION).document(conversation.chatId).set(
        conversation.model_dump(exclude={"id"})
    )


def _send_and_record(conversation: Conversation, text: str) -> None:
    if not text:
        return
    send_message(conversation.chatId, text)
    conversation.messages.append(
        Message(role="agent", text=text, timestamp=dt.datetime.now(dt.timezone.utc).isoformat())
    )


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

    conversation = _get_or_create_conversation(chat_id, parsed.get("item_id"), own_user_id)

    guest_message = Message(
        role="guest",
        text=text,
        timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        imageUrl=image_url,
    )
    conversation.messages.append(guest_message)

    if conversation.activeScenarioId:
        outgoing = continue_scenario(conversation, text, image_url)
    else:
        scenario = find_matching_scenario(text)
        if scenario:
            outgoing = start_scenario(conversation, scenario)
        else:
            reply_text, should_escalate, reason = generate_reply(conversation.messages)
            outgoing = [reply_text] if reply_text else []
            if should_escalate:
                conversation.status = "escalated"
                notify_admin(
                    "⚠️ Диалог требует внимания администратора\n\n"
                    f"Гость: {conversation.guestName or 'без имени'}\n"
                    f"Причина: {reason}\n"
                    f"Сообщение: {text}\n"
                    f"Чат: {chat_id}"
                )

    for message_text in outgoing:
        _send_and_record(conversation, message_text)

    _save_conversation(conversation)
    return {"ok": True}
