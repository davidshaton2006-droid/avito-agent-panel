"""Отправка исходящего сообщения гостю — единая точка входа независимо от
канала (Avito, Instagram, ...), чтобы роуты и вебхуки не ветвились сами."""

from app.firestore_db import Channel


def send_to_guest(channel: Channel, chat_id: str, text: str) -> None:
    if channel == "avito":
        from app.avito_client import send_message

        send_message(chat_id, text)
    elif channel == "instagram":
        from app.instagram_client import send_message

        send_message(chat_id, text)
    else:
        raise ValueError(f"Неизвестный канал: {channel}")
