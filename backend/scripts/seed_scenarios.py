"""
Загружает стартовый сценарий «ОПЛАТИЛ» в Firestore (avito_agent_scenarios).
Запуск: python -m scripts.seed_scenarios (из папки backend).
"""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.firestore_db import SCENARIOS_COLLECTION, get_db  # noqa: E402

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
    collection = db.collection(SCENARIOS_COLLECTION)

    existing = list(collection.where("scenarioId", "==", PAYMENT_SCENARIO["scenarioId"]).limit(1).stream())
    if existing:
        print("Сценарий 'payment_confirmation' уже существует — пропускаем.")
        return

    data = dict(PAYMENT_SCENARIO)
    data["updatedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
    collection.document().set(data)
    print("Сценарий 'ОПЛАТИЛ -> чек -> фамилия -> уведомление' создан.")


if __name__ == "__main__":
    main()
