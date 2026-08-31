import logging

import requests

from app.config import get_settings

log = logging.getLogger("telegram-notify")


def notify_admin(text: str) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_admin_chat_id:
        log.warning("Telegram не настроен (TELEGRAM_BOT_TOKEN / TELEGRAM_ADMIN_CHAT_ID) — уведомление пропущено")
        return

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
