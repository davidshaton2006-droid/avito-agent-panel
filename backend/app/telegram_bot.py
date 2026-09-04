"""
Интерактивное Telegram-меню для управления агентом прямо из чата
«Романтик Агент»: профиль (имя/компания/товары/цель), база знаний
(свободный текст), пауза/резюме, выбор объявлений, баланс ProxyAPI.

Работает через Telegram Bot API webhook (POST /webhook/telegram),
регистрируется один раз через setWebhook (см. README).
"""

import logging

import requests

from app.agent_settings import get_agent_settings, update_agent_settings
from app.avito_client import list_items
from app.config import get_settings
from app.firestore_db import CONVERSATIONS_COLLECTION, KNOWLEDGE_BASE_COLLECTION, TELEGRAM_STATE_COLLECTION, get_db

log = logging.getLogger("telegram-bot")

FIELD_LABELS = {
    "name": "Имя",
    "company": "Компания",
    "products": "Товары/услуги",
    "goal": "Цель общения",
    "knowledgeBaseText": "База знаний (свободный текст)",
}


def _api(method: str, payload: dict) -> dict:
    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    response = requests.post(url, json=payload, timeout=10)
    if not response.ok:
        log.error("Telegram API %s failed: %s", method, response.text)
        return {}
    return response.json()


def _get_awaiting(chat_id: int) -> str | None:
    db = get_db()
    doc = db.collection(TELEGRAM_STATE_COLLECTION).document(str(chat_id)).get()
    if doc.exists:
        return (doc.to_dict() or {}).get("awaiting")
    return None


def _set_awaiting(chat_id: int, awaiting: str | None) -> None:
    db = get_db()
    db.collection(TELEGRAM_STATE_COLLECTION).document(str(chat_id)).set({"awaiting": awaiting})


def _status_summary() -> dict:
    settings_doc = get_agent_settings()
    db = get_db()

    conversations = list(db.collection(CONVERSATIONS_COLLECTION).stream())
    message_count = sum(len((c.to_dict() or {}).get("messages", [])) for c in conversations)

    has_qa_pairs = bool(list(db.collection(KNOWLEDGE_BASE_COLLECTION).limit(1).stream()))
    kb_filled = has_qa_pairs or bool((settings_doc.get("knowledgeBaseText") or "").strip())

    allowed = settings_doc.get("allowedItemIds") or []

    return {
        "isActive": settings_doc.get("isActive", True),
        "message_count": message_count,
        "items_label": str(len(allowed)) if allowed else "все",
        "kb_filled": kb_filled,
    }


def _main_menu() -> tuple[str, dict]:
    status = _status_summary()
    status_icon = "🟢" if status["isActive"] else "⏸️"
    text = (
        f"{status_icon} Нейроагент «Романтик»\n\n"
        f"Сообщений: {status['message_count']}\n"
        f"Объявления: {status['items_label']}\n"
        f"База знаний: {'✅ заполнена' if status['kb_filled'] else '❌ пусто'}"
    )
    pause_button = (
        {"text": "▶️ Возобновить бота", "callback_data": "toggle_active"}
        if not status["isActive"]
        else {"text": "⏸ Приостановить бота", "callback_data": "toggle_active"}
    )
    markup = {
        "inline_keyboard": [
            [{"text": "🏷 Имя", "callback_data": "edit:name"}, {"text": "🏢 Компания", "callback_data": "edit:company"}],
            [
                {"text": "🛍 Товары/услуги", "callback_data": "edit:products"},
                {"text": "🎯 Цель общения", "callback_data": "edit:goal"},
            ],
            [
                {"text": "📚 База знаний", "callback_data": "edit:knowledgeBaseText"},
                {"text": "📌 Выбрать объявления", "callback_data": "items"},
            ],
            [{"text": "💰 Баланс ProxyAPI", "callback_data": "balance"}],
            [pause_button],
        ]
    }
    return text, markup


def _send_main_menu(chat_id: int) -> None:
    text, markup = _main_menu()
    _api("sendMessage", {"chat_id": chat_id, "text": text, "reply_markup": markup})


def _render_main_menu(chat_id: int, message_id: int) -> None:
    text, markup = _main_menu()
    _api("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": markup})


def _items_screen() -> tuple[str, dict]:
    allowed = {str(i) for i in get_agent_settings().get("allowedItemIds") or []}
    try:
        items = list_items()
    except requests.RequestException:
        log.exception("Не удалось получить объявления Avito")
        items = []

    rows = []
    for item in items[:50]:
        item_id = str(item.get("id"))
        checked = "✅" if item_id in allowed else "⬜"
        title = (item.get("title") or item_id)[:40]
        rows.append([{"text": f"{checked} {title}", "callback_data": f"items_toggle:{item_id}"}])
    rows.append([{"text": "🔙 Готово", "callback_data": "menu"}])

    text = "📌 Выберите объявления, на которые агент отвечает:\n(ничего не выбрано = отвечает на все)"
    return text, {"inline_keyboard": rows}


def _handle_balance_request(callback_id: str) -> None:
    settings = get_settings()
    text = "Не удалось получить баланс ProxyAPI"
    try:
        response = requests.get(
            "https://api.proxyapi.ru/proxyapi/balance",
            headers={"Authorization": f"Bearer {settings.anthropic_api_key}"},
            timeout=10,
        )
        if response.ok:
            info = response.json()
            text = f"💰 Баланс ProxyAPI: {info.get('balance')} ₽"
            budget = info.get("budget")
            if budget:
                text += f"\nЛимит: {budget.get('limit')} ₽, использовано: {budget.get('used')} ₽"
        else:
            text = (
                "Не удалось получить баланс — проверьте, включён ли доступ к "
                "балансу для этого ключа в личном кабинете ProxyAPI (Ключи API)."
            )
    except requests.RequestException:
        log.exception("Ошибка запроса баланса ProxyAPI")

    _api("answerCallbackQuery", {"callback_query_id": callback_id, "text": text, "show_alert": True})


def _handle_callback(callback_query: dict) -> None:
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    callback_id = callback_query.get("id")

    if data == "balance":
        _handle_balance_request(callback_id)
        return

    if data == "menu":
        _render_main_menu(chat_id, message_id)

    elif data == "toggle_active":
        current = get_agent_settings().get("isActive", True)
        update_agent_settings({"isActive": not current})
        _render_main_menu(chat_id, message_id)

    elif data == "items":
        text, markup = _items_screen()
        _api("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": markup})

    elif data.startswith("items_toggle:"):
        item_id = data.split(":", 1)[1]
        allowed = {str(i) for i in get_agent_settings().get("allowedItemIds") or []}
        if item_id in allowed:
            allowed.discard(item_id)
        else:
            allowed.add(item_id)
        update_agent_settings({"allowedItemIds": sorted(allowed)})
        text, markup = _items_screen()
        _api("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": markup})

    elif data.startswith("edit:"):
        field = data.split(":", 1)[1]
        _set_awaiting(chat_id, field)
        current_value = get_agent_settings().get(field, "")
        label = FIELD_LABELS.get(field, field)
        _api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    f"✏️ {label}\n\nТекущее значение:\n{current_value or '(пусто)'}\n\n"
                    "Пришлите новый текст следующим сообщением — это полностью заменит текущее значение."
                ),
            },
        )

    _api("answerCallbackQuery", {"callback_query_id": callback_id})


def _handle_text_message(message: dict) -> None:
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if text in ("/start", "/menu"):
        _set_awaiting(chat_id, None)
        _send_main_menu(chat_id)
        return

    awaiting = _get_awaiting(chat_id)
    if awaiting:
        update_agent_settings({awaiting: text})
        _set_awaiting(chat_id, None)
        label = FIELD_LABELS.get(awaiting, awaiting)
        _api("sendMessage", {"chat_id": chat_id, "text": f"✅ «{label}» обновлено."})
        _send_main_menu(chat_id)
        return

    _send_main_menu(chat_id)


def handle_update(update: dict) -> None:
    """Меню работает только в личном чате администратора с ботом. Группа
    «Романтик Агент» используется исключительно как зеркало переписок
    (см. telegram_notify.py) — сообщения оттуда (включая темы гостей)
    здесь намеренно игнорируются, чтобы не отвечать меню прямо в теме
    гостя или в общей теме."""
    if "callback_query" in update:
        chat_type = update["callback_query"].get("message", {}).get("chat", {}).get("type")
        if chat_type == "private":
            _handle_callback(update["callback_query"])
    elif "message" in update and "text" in update.get("message", {}):
        message = update["message"]
        if message.get("chat", {}).get("type") == "private":
            _handle_text_message(message)
