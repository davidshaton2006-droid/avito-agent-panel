"""
Загружает стартовый сценарий «ОПЛАТИЛ» в Firestore (avito_agent_scenarios).
Запуск: python -m scripts.seed_scenarios (из папки backend).
"""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.cloud.firestore_v1.base_query import FieldFilter  # noqa: E402

from app.firestore_db import get_db, scenarios_collection  # noqa: E402

CHANNEL = "avito"

PAYMENT_SCENARIO = {
    "scenarioId": "payment_confirmation",
    "name": "Оплатил -> чек -> фамилия -> уведомление",
    "triggerKeyword": "оплатил",
    "isActive": True,
    "steps": [
        {"type": "message", "text": "Отлично, спасибо! 📸 Пришлите, пожалуйста, фото чека об оплате"},
        {"type": "wait_photo", "saveToField": "paymentReceiptUrl"},
        {"type": "message", "text": "Спасибо, чек получен! ✅ Теперь укажите, пожалуйста, фамилию, на которую оформить бронь"},
        {"type": "wait_text", "saveToField": "bookingSurname"},
        {"type": "notify_admin"},
        {"type": "message", "text": "Приняли ваш чек и данные — проверяем поступление оплаты и подтвердим бронь в ближайшее время. Спасибо за терпение! 🌲"},
    ],
}


def main():
    db = get_db()
    collection = db.collection(scenarios_collection(CHANNEL))

    existing = list(
        collection.where(filter=FieldFilter("scenarioId", "==", PAYMENT_SCENARIO["scenarioId"])).limit(1).stream()
    )
    if existing:
        print("Сценарий 'payment_confirmation' уже существует — пропускаем.")
        return

    data = dict(PAYMENT_SCENARIO)
    data["updatedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
    collection.document().set(data)
    print("Сценарий 'ОПЛАТИЛ -> чек -> фамилия -> уведомление' создан.")


if __name__ == "__main__":
    main()
