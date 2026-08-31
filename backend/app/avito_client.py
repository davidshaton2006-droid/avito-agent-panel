"""
Клиент для Avito Messenger API.

Сверено с официальной OpenAPI-схемой (swagger.json), полученной из
документации Avito для бизнеса. Используется OAuth2 client_credentials —
доступ к возможностям своей же учётной записи (аккаунт базы отдыха), без
авторизации от имени других пользователей.
"""

import logging
import time

import requests

from app.config import get_settings

log = logging.getLogger("avito-client")

TOKEN_URL = "https://api.avito.ru/token"
API_BASE = "https://api.avito.ru"

_token_cache: dict = {"access_token": None, "expires_at": 0}


def get_access_token() -> str:
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    settings = get_settings()
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.avito_client_id,
            "client_secret": settings.avito_client_secret,
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)

    return _token_cache["access_token"]


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }


def subscribe_webhook(callback_url: str):
    """POST /messenger/v3/webhook — регистрирует URL для вебхуков."""
    response = requests.post(
        f"{API_BASE}/messenger/v3/webhook",
        headers=_auth_headers(),
        json={"url": callback_url},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def send_message(chat_id: str, text: str):
    """POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/messages — на данный
    момент Avito поддерживает в этом методе только текстовые сообщения."""
    settings = get_settings()
    response = requests.post(
        f"{API_BASE}/messenger/v1/accounts/{settings.avito_user_id}/chats/{chat_id}/messages",
        headers=_auth_headers(),
        json={"type": "text", "message": {"text": text}},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_chat(chat_id: str) -> dict:
    """GET /messenger/v2/accounts/{user_id}/chats/{chat_id} — данные чата: список
    участников (с именами) и контекст (например, объявление, по которому чат)."""
    settings = get_settings()
    response = requests.get(
        f"{API_BASE}/messenger/v2/accounts/{settings.avito_user_id}/chats/{chat_id}",
        headers=_auth_headers(),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_guest_name(chat_id: str, own_user_id: str) -> str | None:
    """Вебхук не содержит имени отправителя, поэтому имя гостя достаём отдельным
    запросом чата: берём первого участника, который не является нашим аккаунтом."""
    try:
        chat = get_chat(chat_id)
    except requests.RequestException:
        log.exception("Не удалось получить данные чата %s для определения имени гостя", chat_id)
        return None

    for user in chat.get("users", []):
        if str(user.get("id")) != str(own_user_id):
            return user.get("name")
    return None


def get_chat_url(chat_id: str) -> str:
    """Ссылка на переписку в веб-версии Avito, для уведомлений админу.

    В OpenAPI-схеме Messenger API такого поля нет (это чисто API для интеграций,
    без веб-адресов), поэтому используем предположительный, но стандартный для
    Avito формат ссылки на диалог в личном кабинете.
    """
    return f"https://www.avito.ru/profile/messenger/channel/{chat_id}"


def parse_webhook_payload(raw: dict) -> dict:
    """
    Разбирает сырой JSON вебхука Avito (схема WebhookMessage внутри
    payload.value) в плоскую структуру, с которой удобно работать остальному
    приложению.
    """
    log.info("Сырой webhook payload от Avito: %s", raw)
    payload = raw.get("payload", {})

    if payload.get("type") != "message":
        # Пока в схеме API есть только тип "message", но на будущее игнорируем
        # неизвестные типы уведомлений вместо падения.
        return {"chat_id": None}

    value = payload.get("value", {})
    content = value.get("content", {}) or {}

    message_type = value.get("type", "text")
    text = content.get("text") or ""
    image_url = None

    if message_type == "image":
        sizes = (content.get("image") or {}).get("sizes", {})
        # Берём самую большую доступную картинку (обычно "1280x960")
        image_url = sizes.get("1280x960") or next(iter(sizes.values()), None)
    elif message_type == "location":
        location = content.get("location") or {}
        text = location.get("text") or location.get("title") or ""
    elif message_type == "link":
        link = content.get("link") or {}
        text = link.get("url") or link.get("text") or ""
    elif message_type == "item":
        item = content.get("item") or {}
        text = f"{item.get('title', '')} {item.get('item_url', '')}".strip()

    return {
        "chat_id": value.get("chat_id"),
        "text": text,
        "author_id": value.get("author_id"),
        "own_user_id": value.get("user_id"),
        "item_id": value.get("item_id"),
        "message_type": message_type,
        "image_url": image_url,
    }
