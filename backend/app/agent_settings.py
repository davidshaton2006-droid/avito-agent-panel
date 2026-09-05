"""
Редактируемые настройки агента: профиль (имя/компания/товары/цель),
свободный текст базы знаний, пауза/резюме, список объявлений (для Avito), на
которые агент отвечает. Хранится одним документом в Firestore на канал
(avito/instagram), редактируется через Telegram-бота и/или REST API
(используется веб-панелью).

Значения по умолчанию совпадают с прежним статическим системным промптом —
пока админ ничего не менял, поведение агента не меняется.
"""

from app.firestore_db import Channel, SETTINGS_DOC_ID, get_db, settings_collection

DEFAULTS = {
    "isActive": True,
    "name": "менеджер базы Романтик",
    "company": "База отдыха «Романтик»",
    "products": "Сдача в аренду посуточно домиков на эко-базе отдыха",
    "goal": (
        "Ты — вежливый и живой администратор базы отдыха «Романтик». Отвечаешь "
        "гостям на вопросы о базе и бронировании. Общаешься тепло, "
        "по делу, без канцелярита и без шаблонных фраз в духе \"Спасибо за "
        "обращение!\"."
    ),
    "knowledgeBaseText": "",
    "allowedItemIds": [],  # (Avito) пусто = отвечать по всем объявлениям
}


def get_agent_settings(channel: Channel) -> dict:
    db = get_db()
    doc = db.collection(settings_collection(channel)).document(SETTINGS_DOC_ID).get()
    data = dict(DEFAULTS)
    if doc.exists:
        data.update(doc.to_dict() or {})
    return data


def update_agent_settings(channel: Channel, patch: dict) -> dict:
    db = get_db()
    ref = db.collection(settings_collection(channel)).document(SETTINGS_DOC_ID)
    ref.set(patch, merge=True)
    return get_agent_settings(channel)
