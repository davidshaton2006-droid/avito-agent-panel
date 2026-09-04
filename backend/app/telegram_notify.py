import logging

import requests

from app.config import get_settings

log = logging.getLogger("telegram-notify")


def _telegram_configured() -> bool:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_admin_chat_id:
        log.warning("Telegram не настроен (TELEGRAM_BOT_TOKEN / TELEGRAM_ADMIN_CHAT_ID) — операция пропущена")
        return False
    return True


def notify_admin(text: str) -> None:
    """Отправляет важное уведомление в общую (закреплённую) тему группы —
    эскалации, срабатывание сценариев и т.п."""
    if not _telegram_configured():
        return

    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": settings.telegram_admin_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=10,
    )
    if not response.ok:
        log.error("Не удалось отправить уведомление в Telegram: %s", response.text)


def create_conversation_topic(title: str) -> int | None:
    """Создаёт отдельную тему (topic) в супергруппе для нового диалога с
    гостем. Группа должна быть супергруппой с включёнными Topics, а бот —
    админом с правом управления темами. Возвращает message_thread_id или
    None, если Telegram не настроен или создание не удалось (например,
    группа не поддерживает темы) — в этом случае вызывающий код должен
    просто продолжить без темы (сообщения уйдут в общую тему)."""
    if not _telegram_configured():
        return None

    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/createForumTopic"
    response = requests.post(
        url,
        json={"chat_id": settings.telegram_admin_chat_id, "name": title[:128]},
        timeout=10,
    )
    if not response.ok:
        log.warning("Не удалось создать тему в Telegram (группа без Topics?): %s", response.text)
        return None
    return response.json()["result"]["message_thread_id"]


def send_conversation_message(text: str, thread_id: int | None) -> None:
    """Отправляет сообщение в тему конкретного диалога (thread_id) — либо в
    общую тему группы, если у диалога ещё нет своей темы."""
    if not _telegram_configured():
        return

    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_admin_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if thread_id is not None:
        payload["message_thread_id"] = thread_id

    response = requests.post(url, json=payload, timeout=10)
    if not response.ok:
        log.error("Не удалось отправить сообщение переписки в Telegram: %s", response.text)
