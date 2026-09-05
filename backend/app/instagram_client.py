"""
Клиент для Instagram API with Instagram Login (Meta) — отдельный вход,
без привязки к Facebook-странице (в приложении Meta это раздел
"Настройка API для входа в Instagram" / API setup with Instagram login).

Работает через graph.instagram.com, авторизация — Instagram User Access
Token, сгенерированный для конкретного Instagram-аккаунта (romantik_base)
в этом разделе приложения. Разрешения: instagram_business_basic,
instagram_business_manage_comments, instagram_business_manage_messages.
"""

import hashlib
import hmac
import logging

import requests

from app.config import get_settings

log = logging.getLogger("instagram-client")

API_BASE = "https://graph.instagram.com/v21.0"


def send_message(recipient_id: str, text: str):
    """POST /{ig_user_id}/messages — отправка текстового сообщения в личку Instagram."""
    settings = get_settings()
    response = requests.post(
        f"{API_BASE}/{settings.instagram_ig_user_id}/messages",
        params={"access_token": settings.instagram_access_token},
        json={
            "recipient": {"id": recipient_id},
            "message": {"text": text},
            "messaging_type": "RESPONSE",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def verify_signature(body: bytes, signature_header: str | None) -> bool:
    """Проверяет заголовок X-Hub-Signature-256 (HMAC-SHA256 от Instagram App
    Secret), чтобы отличить настоящий вебхук Meta от подделки."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    settings = get_settings()
    if not settings.instagram_app_secret:
        log.warning("INSTAGRAM_APP_SECRET не задан — пропускаем проверку подписи вебхука")
        return True

    expected = hmac.new(
        settings.instagram_app_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


def get_guest_name(sender_id: str) -> str | None:
    """GET /{ig_scoped_id}?fields=name,username — имя/юзернейм отправителя.
    Instagram отдаёт IGSID (id, привязанный к конкретному Instagram-аккаунту
    получателя), не сам Instagram user id, поэтому запрос идёт напрямую по
    этому id."""
    settings = get_settings()
    try:
        response = requests.get(
            f"{API_BASE}/{sender_id}",
            params={"fields": "name,username", "access_token": settings.instagram_access_token},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("name") or data.get("username")
    except requests.RequestException:
        log.exception("Не удалось получить имя гостя Instagram %s", sender_id)
        return None


def parse_webhook_payload(raw: dict) -> dict | None:
    """
    Разбирает один messaging-элемент вебхука Instagram (entry[].messaging[])
    в ту же плоскую структуру, что и app.avito_client.parse_webhook_payload,
    чтобы дальше их можно было обрабатывать одинаково.

    Возвращает None, если в пейлоаде нет ни одного применимого сообщения
    (например, это событие о прочтении/доставке).
    """
    log.info("Сырой webhook payload от Instagram: %s", raw)
    settings = get_settings()

    for entry in raw.get("entry", []):
        for event in entry.get("messaging", []):
            message = event.get("message")
            if not message or message.get("is_echo"):
                # is_echo — наше же исходящее сообщение, отражённое вебхуком,
                # его игнорируем так же, как эхо в Avito.
                continue

            sender_id = event.get("sender", {}).get("id")
            text = message.get("text") or ""
            image_url = None
            for attachment in message.get("attachments") or []:
                if attachment.get("type") == "image":
                    image_url = (attachment.get("payload") or {}).get("url")
                    break

            if not text and not image_url:
                continue

            return {
                "chat_id": sender_id,
                "text": text,
                "author_id": sender_id,
                "own_user_id": settings.instagram_ig_user_id,
                "item_id": None,
                "image_url": image_url,
            }
    return None
