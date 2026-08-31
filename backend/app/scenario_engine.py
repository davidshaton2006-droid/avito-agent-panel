"""
Движок пошаговых сценариев (например «ОПЛАТИЛ» -> чек -> фамилия ->
уведомление админу). Сценарии хранятся в avito_agent_scenarios и полностью
настраиваются через админку — этот модуль просто исполняет шаги.

Финальное подтверждение брони гостю НЕ отправляется автоматически —
после notify_admin бот отправляет только "проверяем оплату", а
подтверждение администратор шлёт вручную через панель переписок.
"""

import logging

from google.cloud.firestore_v1.base_query import FieldFilter

from app.avito_client import get_chat_url, send_message
from app.firestore_db import SCENARIOS_COLLECTION, get_db
from app.models import Conversation, Scenario
from app.telegram_notify import notify_admin

log = logging.getLogger("scenario-engine")


def find_matching_scenario(text: str) -> Scenario | None:
    db = get_db()
    docs = db.collection(SCENARIOS_COLLECTION).where(filter=FieldFilter("isActive", "==", True)).stream()
    normalized = text.strip().lower()
    for doc in docs:
        data = doc.to_dict()
        trigger = (data.get("triggerKeyword") or "").strip().lower()
        if trigger and trigger == normalized:
            data["id"] = doc.id
            return Scenario(**data)
    return None


def _get_scenario(scenario_id: str) -> Scenario | None:
    db = get_db()
    doc = db.collection(SCENARIOS_COLLECTION).document(scenario_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return Scenario(**data)


def start_scenario(conversation: Conversation, scenario: Scenario) -> list[str]:
    """Starts a scenario on a conversation, running steps until one that
    waits on guest input. Returns guest-facing message texts to send."""
    conversation.activeScenarioId = scenario.id
    conversation.activeStepIndex = 0
    conversation.scenarioData = {}
    return _run_from_current_step(conversation, scenario)


def continue_scenario(
    conversation: Conversation, incoming_text: str, incoming_image_url: str | None
) -> list[str]:
    """Advances a conversation that is mid-scenario, given the guest's latest
    message. Returns guest-facing message texts to send."""
    scenario = _get_scenario(conversation.activeScenarioId)
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
    return _run_from_current_step(conversation, scenario)


def _run_from_current_step(conversation: Conversation, scenario: Scenario) -> list[str]:
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
            _send_admin_notification(conversation)
            conversation.activeStepIndex = step_index + 1
            continue

        if step.type in ("wait_photo", "wait_text"):
            # Pause here until the guest replies
            break

    return outgoing


def _send_admin_notification(conversation: Conversation) -> None:
    guest_name = conversation.guestName or "гость без имени"
    surname = conversation.scenarioData.get("bookingSurname", "не указана")
    receipt_url = conversation.scenarioData.get("paymentReceiptUrl", "нет ссылки")
    chat_url = get_chat_url(conversation.chatId)

    text = (
        "💰 Новая оплата ожидает подтверждения\n\n"
        f"Гость: {guest_name}\n"
        f"Фамилия для брони: {surname}\n"
        f"Чат Avito: {chat_url}\n"
        f"Фото чека: {receipt_url}"
    )
    notify_admin(text)


def send_to_guest(chat_id: str, text: str) -> None:
    send_message(chat_id, text)
