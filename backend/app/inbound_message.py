"""
Общая логика обработки входящего сообщения от гостя — одинаковая для любого
канала (Avito, Instagram, ...). Канало-специфичные вебхуки (routes/webhook.py,
routes/instagram_webhook.py) занимаются только разбором своего формата
пейлоада и вызывают эти функции.
"""

import datetime as dt
import logging
from typing import Callable

from app.agent_settings import get_agent_settings
from app.channel_send import send_to_guest
from app.claude_agent import generate_reply
from app.firestore_db import Channel, conversations_collection, get_db
from app.models import Conversation, Message
from app.scenario_engine import continue_scenario, find_matching_scenario, start_scenario
from app.telegram_notify import create_conversation_topic, notify_admin, send_conversation_message

log = logging.getLogger("inbound-message")

CHANNEL_ICON = {"avito": "🅰️", "instagram": "📷"}


def get_or_create_conversation(
    channel: Channel,
    chat_id: str,
    item_id: str | None,
    resolve_guest_name: Callable[[], str | None],
) -> Conversation:
    """`resolve_guest_name` is only called for a brand-new conversation (it
    typically costs an extra API call to the channel) — never for a chat we
    already know about."""
    db = get_db()
    ref = db.collection(conversations_collection(channel)).document(chat_id)
    doc = ref.get()
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    if doc.exists:
        return Conversation(id=doc.id, **doc.to_dict())

    guest_name = resolve_guest_name()
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
    icon = CHANNEL_ICON.get(channel, "")
    conversation.telegramThreadId = create_conversation_topic(f"{icon} {guest_name or f'Чат {chat_id}'}".strip())
    ref.set(conversation.model_dump(exclude={"id"}))
    return conversation


def save_conversation(channel: Channel, conversation: Conversation) -> None:
    db = get_db()
    conversation.updatedAt = dt.datetime.now(dt.timezone.utc).isoformat()
    db.collection(conversations_collection(channel)).document(conversation.chatId).set(
        conversation.model_dump(exclude={"id"})
    )


def _send_and_record(channel: Channel, conversation: Conversation, text: str) -> None:
    if not text:
        return
    send_to_guest(channel, conversation.chatId, text)
    conversation.messages.append(
        Message(role="agent", text=text, timestamp=dt.datetime.now(dt.timezone.utc).isoformat())
    )
    send_conversation_message(f"🤖 {text}", conversation.telegramThreadId)


def process_guest_message(channel: Channel, conversation: Conversation, text: str, image_url: str | None) -> None:
    """Records the guest message, mirrors it to Telegram, then — unless the
    agent is paused or this listing isn't in the allowlist — runs the
    scenario engine or Claude and sends+records any replies. Caller persists
    the conversation afterwards via save_conversation()."""
    guest_message = Message(
        role="guest",
        text=text,
        timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        imageUrl=image_url,
    )
    conversation.messages.append(guest_message)
    send_conversation_message(
        f"👤 {text}" + (f"\n📎 {image_url}" if image_url else ""), conversation.telegramThreadId
    )

    agent_settings = get_agent_settings(channel)
    allowed_items = {str(i) for i in agent_settings.get("allowedItemIds") or []}
    item_allowed = not allowed_items or (
        conversation.itemId is not None and str(conversation.itemId) in allowed_items
    )

    if not agent_settings.get("isActive", True) or not item_allowed:
        # Бот на паузе, либо это объявление не выбрано для автоответов —
        # сообщение гостя всё равно сохранено и видно в Telegram-теме,
        # но агент не отвечает — ждёт ручной реакции администратора.
        return

    if conversation.activeScenarioId:
        outgoing = continue_scenario(channel, conversation, text, image_url)
    else:
        scenario = find_matching_scenario(channel, text)
        if scenario:
            outgoing = start_scenario(channel, conversation, scenario)
        else:
            reply_text, should_escalate, reason = generate_reply(channel, conversation.messages)
            outgoing = [reply_text] if reply_text else []
            if should_escalate:
                conversation.status = "escalated"
                notify_admin(
                    "⚠️ Диалог требует внимания администратора\n\n"
                    f"Канал: {channel}\n"
                    f"Гость: {conversation.guestName or 'без имени'}\n"
                    f"Причина: {reason}\n"
                    f"Сообщение: {text}\n"
                    f"Чат: {conversation.chatId}"
                )

    for message_text in outgoing:
        _send_and_record(channel, conversation, message_text)
