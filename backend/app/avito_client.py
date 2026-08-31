"""
Клиент для Avito Messenger API.

ВАЖНО: основан на предоставленном референсном коде (документированные
официальные принципы работы Avito API: OAuth2 client_credentials, вебхуки,
методы для чатов/сообщений). Точные названия полей в JSON вебхука и
эндпоинтов нужно сверить с реальной документацией на developers.avito.ru
после получения доступа — она закрытая. Места, где это критично, помечены
TODO ниже; поправь их по факту первого реального вебхука.
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
    response = requests.post(
        f"{API_BASE}/messenger/v3/webhook",
        headers=_auth_headers(),
        json={"url": callback_url},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def send_message(chat_id: str, text: str):
    settings = get_settings()
    response = requests.post(
        f"{API_BASE}/messenger/v1/accounts/{settings.avito_user_id}/chats/{chat_id}/messages",
        headers=_auth_headers(),
        json={"message": {"text": text}, "type": "text"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_chat_url(chat_id: str) -> str:
    """Ссылка на переписку в веб-версии Avito, для уведомлений админу."""
    # TODO: сверить реальный формат ссылки на чат после первого доступа к API —
    # это предположительный (наиболее вероятный) вид URL мессенджера Avito.
    return f"https://www.avito.ru/profile/messenger/channel/{chat_id}"


def parse_webhook_payload(raw: dict) -> dict:
    """
    Разбирает сырой JSON вебхука Avito в плоскую структуру, с которой удобно
    работать остальному приложению.

    TODO: после первого реального вебхука проверить:
    - точное имя поля с типом сообщения (image/text/...)
    - как именно передаётся URL фото (message.content.image.sizes["1280x960"]
      судя по открытым интеграциям с Avito API, но требует подтверждения)
    - поле с именем гостя (author_name / user.name / etc.)
    """
    log.info("Сырой webhook payload от Avito: %s", raw)
    payload = raw.get("payload", raw)
    message = payload.get("message", {})
    content = message.get("content", {})

    message_type = message.get("type", "text")
    image_url = None
    if message_type == "image":
        image = content.get("image", {})
        sizes = image.get("sizes", {})
        # Берём самую большую доступную картинку
        image_url = next(iter(sizes.values()), None) if sizes else image.get("url")

    return {
        "chat_id": payload.get("chat_id"),
        "text": message.get("text") or content.get("text", ""),
        "author_id": message.get("author_id"),
        "author_name": payload.get("author_name") or payload.get("user", {}).get("name"),
        "item_id": payload.get("item_id"),
        "message_type": message_type,
        "image_url": image_url,
    }
