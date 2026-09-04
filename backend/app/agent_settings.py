"""
Редактируемые настройки агента: профиль (имя/компания/товары/цель),
свободный текст базы знаний, пауза/резюме, список объявлений, на которые
агент отвечает. Хранится одним документом в Firestore, редактируется через
Telegram-бота и/или REST API (используется веб-панелью).

Значения по умолчанию совпадают с текущим статическим системным промптом —
пока админ ничего не менял, поведение агента не меняется.
"""

from app.firestore_db import SETTINGS_COLLECTION, SETTINGS_DOC_ID, get_db

DEFAULTS = {
    "isActive": True,
    "name": "менеджер базы Романтик",
    "company": "База отдыха «Романтик»",
    "products": "Сдача в аренду посуточно домиков на эко-базе отдыха",
    "goal": (
        "Ты — вежливый и живой администратор базы отдыха «Романтик». Отвечаешь "
        "гостям на Авито на вопросы о базе и бронировании. Общаешься тепло, "
        "по делу, без канцелярита и без шаблонных фраз в духе \"Спасибо за "
        "обращение!\"."
    ),
    "knowledgeBaseText": "",
    "allowedItemIds": [],  # пусто = отвечать по всем объявлениям
}


def get_agent_settings() -> dict:
    db = get_db()
    doc = db.collection(SETTINGS_COLLECTION).document(SETTINGS_DOC_ID).get()
    data = dict(DEFAULTS)
    if doc.exists:
        data.update(doc.to_dict() or {})
    return data


def update_agent_settings(patch: dict) -> dict:
    db = get_db()
    ref = db.collection(SETTINGS_COLLECTION).document(SETTINGS_DOC_ID)
    ref.set(patch, merge=True)
    return get_agent_settings()
