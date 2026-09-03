"""
Только для чтения: проверка свободных домиков на сайте бронирования
(romatik-client2, Firebase-проект "romantik-client", коллекция "bookings").

Логика повторяет calculateAvailability() из romatik-client2 (src/lib/firebase/bookings.ts):
7 двухместных домиков, 10 трёхместных, занятость считается по пересечению
дат check_in/check_out, отменённые бронирования (payment_status == "canceled")
не учитываются.
"""

import datetime as dt
import json
import logging
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore

from app.config import get_settings

log = logging.getLogger("booking-availability")

BOOKINGS_COLLECTION = "bookings"
TOTAL_TWO_SEAT = 7
TOTAL_THREE_SEAT = 10

_APP_NAME = "booking_site"


@lru_cache
def _get_booking_db():
    settings = get_settings()
    if not settings.booking_firebase_service_account_json:
        return None

    try:
        app = firebase_admin.get_app(_APP_NAME)
    except ValueError:
        raw = settings.booking_firebase_service_account_json
        if raw.strip().startswith("{"):
            cred = credentials.Certificate(json.loads(raw))
        else:
            cred = credentials.Certificate(raw)
        app = firebase_admin.initialize_app(
            cred, {"projectId": settings.booking_firebase_project_id}, name=_APP_NAME
        )
    return firestore.client(app)


def _parse_date(value) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def check_availability(check_in: str, check_out: str) -> dict:
    """Считает свободные домики на сайте бронирования на заданный период.

    Возвращает {"available_two_seat", "available_three_seat", "total_two_seat",
    "total_three_seat"} либо {"error": "..."}, если синхронизация недоступна
    или даты некорректны.
    """
    db = _get_booking_db()
    if db is None:
        return {"error": "Синхронизация с сайтом бронирования не настроена"}

    start = _parse_date(check_in)
    end = _parse_date(check_out)
    if not start or not end or start >= end:
        return {"error": "Некорректные даты: нужен формат YYYY-MM-DD, дата заезда раньше даты выезда"}

    occupied_two_seat = 0
    occupied_three_seat = 0

    try:
        docs = list(db.collection(BOOKINGS_COLLECTION).stream())
    except Exception:
        log.exception("Не удалось получить бронирования с сайта romatik-client2")
        return {"error": "Не удалось получить данные с сайта бронирования"}

    for doc in docs:
        data = doc.to_dict() or {}
        # Бронирования с сайта отмечают отмену через payment_status, а
        # пришедшие через TravelLine (worker/src/travelline.ts в romatik-client2,
        # включая брони с других OTA-каналов вроде Avito) — через travelline_status.
        if data.get("payment_status") == "canceled" or data.get("travelline_status") == "Cancelled":
            continue

        b_start = _parse_date(data.get("check_in"))
        b_end = _parse_date(data.get("check_out"))
        if not b_start or not b_end:
            continue

        # Пересечение периодов: занято, если заезд раньше конца брони И выезд позже начала брони
        if b_start < end and b_end > start:
            house_type = data.get("house_type")
            if house_type == "Двухместный":
                occupied_two_seat += 1
            elif house_type == "Трехместный":
                occupied_three_seat += 1

    return {
        "available_two_seat": max(0, TOTAL_TWO_SEAT - occupied_two_seat),
        "available_three_seat": max(0, TOTAL_THREE_SEAT - occupied_three_seat),
        "total_two_seat": TOTAL_TWO_SEAT,
        "total_three_seat": TOTAL_THREE_SEAT,
    }
