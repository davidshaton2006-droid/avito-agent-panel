"""
Интерактивное Telegram-меню для управления агентом прямо из чата
«Романтик Агент»: профиль (имя/компания/товары/цель), база знаний
(свободный текст), пауза/резюме, выбор объявлений (Avito), баланс ProxyAPI.

Работает через Telegram Bot API webhook (POST /webhook/telegram),
регистрируется один раз через setWebhook (см. README).

Поддерживает несколько каналов (Avito, Instagram, ...) — любое действие
редактирования начинается с выбора канала, дальше меню то же самое,
просто скопировано на данные этого канала.
"""

import logging

import requests

from app.agent_settings import get_agent_settings, update_agent_settings
from app.avito_client import list_items
from app.config import get_settings
from app.firestore_db import (
    CHANNELS,
    Channel,
    conversations_collection,
    get_db,
    knowledge_base_collection,
    telegram_state_collection,
)

log = logging.getLogger("telegram-bot")

CHANNEL_LABELS: dict[Channel, str] = {"avito": "🅰️ Avito", "instagram": "📷 Instagram"}

FIELD_LABELS = {
    "name": "Имя",
    "company": "Компания",
    "products": "Товары/услуги",
    "goal": "Цель общения",
    "knowledgeBaseText": "База знаний (свободный текст)",
}

# У какого документа хранится состояние ожидания ввода — общее для бота
# (один администратор, один личный чат), не по каналу.
_STATE_DOC_ID = "state"


def _api(method: str, payload: dict) -> dict:
    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    response = requests.post(url, json=payload, timeout=10)
    if not response.ok:
        log.error("Telegram API %s failed: %s", method, response.text)
        return {}
    return response.json()


def _get_awaiting(chat_id: int) -> dict | None:
    db = get_db()
    doc = db.collection(telegram_state_collection("avito")).document(str(chat_id)).get()
    if doc.exists:
        return (doc.to_dict() or {}).get("awaiting")
    return None


def _set_awaiting(chat_id: int, awaiting: dict | None) -> None:
    db = get_db()
    db.collection(telegram_state_collection("avito")).document(str(chat_id)).set({"awaiting": awaiting})


# --- Экран выбора канала -----------------------------------------------


def _channel_picker() -> tuple[str, dict]:
    text = "Выберите канал для настройки:"
    markup = {
        "inline_keyboard": [[{"text": CHANNEL_LABELS[ch], "callback_data": f"channel:{ch}"}] for ch in CHANNELS]
    }
    return text, markup


def _send_channel_picker(chat_id: int) -> None:
    text, markup = _channel_picker()
    _api("sendMessage", {"chat_id": chat_id, "text": text, "reply_markup": markup})


# --- Главное меню канала -------------------------------------------------


def _status_summary(channel: Channel) -> dict:
    settings_doc = get_agent_settings(channel)
    db = get_db()

    conversations = list(db.collection(conversations_collection(channel)).stream())
    message_count = sum(len((c.to_dict() or {}).get("messages", [])) for c in conversations)

    has_qa_pairs = bool(list(db.collection(knowledge_base_collection(channel)).limit(1).stream()))
    kb_filled = has_qa_pairs or bool((settings_doc.get("knowledgeBaseText") or "").strip())

    allowed = settings_doc.get("allowedItemIds") or []

    return {
        "isActive": settings_doc.get("isActive", True),
        "message_count": message_count,
        "items_label": str(len(allowed)) if allowed else "все",
        "kb_filled": kb_filled,
    }


def _main_menu(channel: Channel) -> tuple[str, dict]:
    status = _status_summary(channel)
    status_icon = "🟢" if status["isActive"] else "⏸️"
    text = (
        f"{CHANNEL_LABELS[channel]}\n"
        f"{status_icon} Нейроагент «Романтик»\n\n"
        f"Сообщений: {status['message_count']}\n"
    )
    if channel == "avito":
        text += f"Объявления: {status['items_label']}\n"
    text += f"База знаний: {'✅ заполнена' if status['kb_filled'] else '❌ пусто'}"

    pause_button = (
        {"text": "▶️ Возобновить бота", "callback_data": f"toggle_active:{channel}"}
        if not status["isActive"]
        else {"text": "⏸ Приостановить бота", "callback_data": f"toggle_active:{channel}"}
    )

    rows = [
        [
            {"text": "🏷 Имя", "callback_data": f"edit:{channel}:name"},
            {"text": "🏢 Компания", "callback_data": f"edit:{channel}:company"},
        ],
        [
            {"text": "🛍 Товары/услуги", "callback_data": f"edit:{channel}:products"},
            {"text": "🎯 Цель общения", "callback_data": f"edit:{channel}:goal"},
        ],
        [{"text": "📚 База знаний", "callback_data": f"edit:{channel}:knowledgeBaseText"}],
    ]
    if channel == "avito":
        rows.append([{"text": "📌 Выбрать объявления", "callback_data": f"items:{channel}"}])
    rows.append([{"text": "💰 Баланс ProxyAPI", "callback_data": "balance"}])
    rows.append([pause_button])
    rows.append([{"text": "🔙 Сменить канал", "callback_data": "channels"}])

    return text, {"inline_keyboard": rows}


def _send_main_menu(chat_id: int, channel: Channel) -> None:
    text, markup = _main_menu(channel)
    _api("sendMessage", {"chat_id": chat_id, "text": text, "reply_markup": markup})


def _render_main_menu(chat_id: int, message_id: int, channel: Channel) -> None:
    text, markup = _main_menu(channel)
    _api("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": markup})


def _render_channel_picker(chat_id: int, message_id: int) -> None:
    text, markup = _channel_picker()
    _api("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": markup})


# --- Выбор объявлений (только Avito) -------------------------------------


def _items_screen(channel: Channel) -> tuple[str, dict]:
    allowed = {str(i) for i in get_agent_settings(channel).get("allowedItemIds") or []}
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
        rows.append([{"text": f"{checked} {title}", "callback_data": f"items_toggle:{channel}:{item_id}"}])
    rows.append([{"text": "🔙 Готово", "callback_data": f"menu:{channel}"}])

    text = "📌 Выберите объявления, на которые агент отвечает:\n(ничего не выбрано = отвечает на все)"
    return text, {"inline_keyboard": rows}


# --- Баланс ProxyAPI (общий для всех каналов) -----------------------------


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


# --- Обработка нажатий кнопок ---------------------------------------------


def _handle_callback(callback_query: dict) -> None:
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    callback_id = callback_query.get("id")

    if data == "balance":
        _handle_balance_request(callback_id)
        return

    if data == "channels":
        _render_channel_picker(chat_id, message_id)

    elif data.startswith("channel:"):
        channel = data.split(":", 1)[1]
        _render_main_menu(chat_id, message_id, channel)

    elif data.startswith("menu:"):
        channel = data.split(":", 1)[1]
        _render_main_menu(chat_id, message_id, channel)

    elif data.startswith("toggle_active:"):
        channel = data.split(":", 1)[1]
        current = get_agent_settings(channel).get("isActive", True)
        update_agent_settings(channel, {"isActive": not current})
        _render_main_menu(chat_id, message_id, channel)

    elif data.startswith("items_toggle:"):
        _, channel, item_id = data.split(":", 2)
        allowed = {str(i) for i in get_agent_settings(channel).get("allowedItemIds") or []}
        if item_id in allowed:
            allowed.discard(item_id)
        else:
            allowed.add(item_id)
        update_agent_settings(channel, {"allowedItemIds": sorted(allowed)})
        text, markup = _items_screen(channel)
        _api("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": markup})

    elif data.startswith("items:"):
        channel = data.split(":", 1)[1]
        text, markup = _items_screen(channel)
        _api("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": markup})

    elif data.startswith("edit:"):
        _, channel, field = data.split(":", 2)
        _set_awaiting(chat_id, {"channel": channel, "field": field})
        current_value = get_agent_settings(channel).get(field, "")
        label = FIELD_LABELS.get(field, field)
        _api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    f"{CHANNEL_LABELS[channel]} — ✏️ {label}\n\nТекущее значение:\n{current_value or '(пусто)'}\n\n"
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
        _send_channel_picker(chat_id)
        return

    awaiting = _get_awaiting(chat_id)
    if awaiting:
        channel = awaiting["channel"]
        field = awaiting["field"]
        update_agent_settings(channel, {field: text})
        _set_awaiting(chat_id, None)
        label = FIELD_LABELS.get(field, field)
        _api("sendMessage", {"chat_id": chat_id, "text": f"✅ {CHANNEL_LABELS[channel]} — «{label}» обновлено."})
        _send_main_menu(chat_id, channel)
        return

    _send_channel_picker(chat_id)


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
