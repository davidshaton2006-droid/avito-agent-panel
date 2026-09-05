"""
Движок пошаговых сценариев (например «ОПЛАТИЛ» -> чек -> фамилия ->
уведомление админу). Сценарии хранятся в {channel}_agent_scenarios и
полностью настраиваются через админку — этот модуль просто исполняет шаги.
Работает одинаково для любого канала (Avito, Instagram, ...).

Финальное подтверждение брони гостю НЕ отправляется автоматически —
после notify_admin бот отправляет только "проверяем оплату", а
подтверждение администратор шлёт вручную через панель переписок.
"""

import logging

from google.cloud.firestore_v1.base_query import FieldFilter

from app.firestore_db import Channel, get_db, scenarios_collection
from app.models import Conversation, Scenario
from app.telegram_notify import notify_admin

log = logging.getLogger("scenario-engine")


def find_matching_scenario(channel: Channel, text: str) -> Scenario | None:
    db = get_db()
    docs = db.collection(scenarios_collection(channel)).where(filter=FieldFilter("isActive", "==", True)).stream()
    normalized = text.strip().lower()
    for doc in docs:
        data = doc.to_dict()
        trigger = (data.get("triggerKeyword") or "").strip().lower()
        if trigger and trigger == normalized:
            data["id"] = doc.id
            return Scenario(**data)
    return None


def _get_scenario(channel: Channel, scenario_id: str) -> Scenario | None:
    db = get_db()
    doc = db.collection(scenarios_collection(channel)).document(scenario_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return Scenario(**data)


def start_scenario(channel: Channel, conversation: Conversation, scenario: Scenario) -> list[str]:
    """Starts a scenario on a conversation, running steps until one that
    waits on guest input. Returns guest-facing message texts to send."""
    conversation.activeScenarioId = scenario.id
    conversation.activeStepIndex = 0
    conversation.scenarioData = {}
    return _run_from_current_step(channel, conversation, scenario)


def continue_scenario(
    channel: Channel, conversation: Conversation, incoming_text: str, incoming_image_url: str | None
) -> list[str]:
    """Advances a conversation that is mid-scenario, given the guest's latest
    message. Returns guest-facing message texts to send."""
    scenario = _get_scenario(channel, conversation.activeScenarioId)
    if scenario is None:
        conversation.activeScenarioId = None
        conversation.activeStepIndex = None
        return []

    step_index = conversation.activeStepIndex or 0
    if step_index >= len(scenario.steps):
        conversation.activeScenarioId = None
        conversation.activeStepIndex = None
        return []

    step = scenario.steps[step_index]

    if step.type == "wait_photo":
        if not incoming_image_url:
            return ["Пришлите, пожалуйста, именно фото — текстом чек принять не получится 🙂"]
        if step.saveToField:
            conversation.scenarioData[step.saveToField] = incoming_image_url
    elif step.type == "wait_text":
        if not incoming_text.strip():
            return ["Уточните, пожалуйста, текстом."]
        if step.saveToField:
            conversation.scenarioData[step.saveToField] = incoming_text.strip()
    else:
        # Not a step that waits on the guest — nothing to do here
        return []

    conversation.activeStepIndex = step_index + 1
    return _run_from_current_step(channel, conversation, scenario)


def _run_from_current_step(channel: Channel, conversation: Conversation, scenario: Scenario) -> list[str]:
    outgoing: list[str] = []
    while True:
        step_index = conversation.activeStepIndex or 0
        if step_index >= len(scenario.steps):
            conversation.activeScenarioId = None
            conversation.activeStepIndex = None
            break

        step = scenario.steps[step_index]

        if step.type == "message":
            if step.text:
                outgoing.append(step.text)
            conversation.activeStepIndex = step_index + 1
            continue

        if step.type == "notify_admin":
            _send_admin_notification(channel, conversation)
            conversation.activeStepIndex = step_index + 1
            continue

        if step.type in ("wait_photo", "wait_text"):
            # Pause here until the guest replies
            break

    return outgoing


def _get_chat_url(channel: Channel, chat_id: str) -> str | None:
    if channel == "avito":
        from app.avito_client import get_chat_url

        return get_chat_url(chat_id)
    return None


def _send_admin_notification(channel: Channel, conversation: Conversation) -> None:
    guest_name = conversation.guestName or "гость без имени"
    surname = conversation.scenarioData.get("bookingSurname", "не указана")
    receipt_url = conversation.scenarioData.get("paymentReceiptUrl", "нет ссылки")
    chat_url = _get_chat_url(channel, conversation.chatId)

    text = (
        "💰 Новая оплата ожидает подтверждения\n\n"
        f"Канал: {channel}\n"
        f"Гость: {guest_name}\n"
        f"Фамилия для брони: {surname}\n"
        + (f"Чат: {chat_url}\n" if chat_url else f"Chat ID: {conversation.chatId}\n")
        + f"Фото чека: {receipt_url}"
    )
    notify_admin(text)
