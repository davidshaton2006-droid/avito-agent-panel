"""
Реальная доступность домиков через TravelLine PMS Universal API v2 —
физические номера (GET /rooms) минус фактически занятые в запрошенный
период (GET /reservations/search + детали по каждой брони).

В отличие от Search API (используется для поиска вариантов гостем и
подчиняется тарифным правилам — минимальный срок проживания, горизонт
продаж и т.п.), PMS API отражает реальное состояние номерного фонда в
системе управления отелем TL:WebPMS — не зависит от того, через какой
канал пришла бронь. Требует тариф с включённым PMS API (недоступно на
LITE без отдельной платной опции).

Отдельное подключение (свои client_id/secret), не связанное с
Cloudflare-воркером romatik-client2 — это упрощает архитектуру: бот
проверяет доступность напрямую у TravelLine, не трогая Firestore сайта
и не рискуя испортить его данные (см. историю с Search API-синхронизацией,
которая один раз уже записала ложные данные в базу сайта).
"""

import datetime as dt
import logging
import time

import requests

from app.config import get_settings

log = logging.getLogger("travelline-pms")

TL_AUTH_URL = "https://partner.tlintegration.com/auth/token"
TL_API_BASE = "https://partner.tlintegration.com/api"

# Те же room type id, что и в остальных интеграциях с этим объектом TravelLine
# (Read Reservation API, worker romatik-client2) — общая настройка объекта.
ROOM_TYPE_TO_HOUSE_TYPE = {
    "412497": "two_seat",
    "412498": "three_seat",
}

_token_cache: dict = {"access_token": None, "expires_at": 0}
_rooms_cache: dict = {"rooms": None, "expires_at": 0}

ROOMS_CACHE_SECONDS = 1800  # физический номерной фонд меняется очень редко

# Плановые закрытия базы (например, на техобслуживание отопления) — это
# ручные блокировки в календаре TravelLine, которые PMS API НЕ показывает
# (только реальные бронирования), поэтому считаем их отдельно здесь, а не
# полагаемся на модель, чтобы удержать их в голове из текста промпта.
# Формат: (дата начала, дата конца) — обе включительно, это ночи, в которые
# база закрыта для гостей. Обновляйте этот список при новых объявлениях о
# техобслуживании.
CLOSURES: list[tuple[dt.date, dt.date]] = [
    (dt.date(2026, 9, 27), dt.date(2026, 10, 1)),
    (dt.date(2026, 10, 4), dt.date(2026, 10, 8)),
    (dt.date(2026, 10, 11), dt.date(2026, 10, 15)),
]

WEEKDAY_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
WEEKDAY_RATE = 7000  # Пн-Чт
WEEKEND_RATE = 9000  # Пт-Вс


def _night_rate(night: dt.date) -> int:
    return WEEKEND_RATE if night.weekday() >= 4 else WEEKDAY_RATE  # 4=пт, 5=сб, 6=вс


def _price_breakdown(start: dt.date, end: dt.date) -> tuple[list[dict], int]:
    nights = []
    total = 0
    d = start
    while d < end:
        rate = _night_rate(d)
        nights.append({"date": d.isoformat(), "weekday_ru": WEEKDAY_RU[d.weekday()], "rate": rate})
        total += rate
        d += dt.timedelta(days=1)
    return nights, total


def _closed_nights(start: dt.date, end: dt.date) -> list[str]:
    closed = []
    d = start
    while d < end:
        if any(closure_start <= d <= closure_end for closure_start, closure_end in CLOSURES):
            closed.append(d.isoformat())
        d += dt.timedelta(days=1)
    return closed


def _get_token() -> str:
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    settings = get_settings()
    response = requests.post(
        TL_AUTH_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.travelline_client_id,
            "client_secret": settings.travelline_client_secret,
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)
    return _token_cache["access_token"]


def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_token()}"}


def _get_rooms() -> list[dict]:
    if _rooms_cache["rooms"] is not None and time.time() < _rooms_cache["expires_at"]:
        return _rooms_cache["rooms"]

    settings = get_settings()
    rooms: list[dict] = []
    page_token: str | None = None

    while True:
        params: dict = {"pageToken": page_token} if page_token else {"maxPageSize": 100}
        response = requests.get(
            f"{TL_API_BASE}/pms/v2/properties/{settings.travelline_property_id}/rooms",
            headers=_headers(),
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        rooms.extend(data.get("rooms", []))
        if not data.get("hasNextPage"):
            break
        page_token = data.get("nextPageToken")

    _rooms_cache["rooms"] = rooms
    _rooms_cache["expires_at"] = time.time() + ROOMS_CACHE_SECONDS
    return rooms


def _search_active_reservation_numbers(start: dt.date, end: dt.date) -> list[str]:
    settings = get_settings()
    numbers: list[str] = []
    page_token: str | None = None
    start_str = f"{start.isoformat()}T00:00"
    end_str = f"{end.isoformat()}T23:59"

    while True:
        params: dict = (
            {"pageToken": page_token}
            if page_token
            else {
                "state": "Active",
                "startAffectPeriodDateTime": start_str,
                "endAffectPeriodDateTime": end_str,
                "maxPageSize": 100,
            }
        )
        response = requests.get(
            f"{TL_API_BASE}/pms/v2/properties/{settings.travelline_property_id}/reservations/search",
            headers=_headers(),
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        numbers.extend(r["number"] for r in data.get("reservations", []) if r.get("number"))
        if not data.get("hasNextPage"):
            break
        page_token = data.get("nextPageToken")

    return numbers


def _get_reservation(number: str) -> dict:
    settings = get_settings()
    response = requests.get(
        f"{TL_API_BASE}/pms/v2/properties/{settings.travelline_property_id}/reservations/{number}",
        headers=_headers(),
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get("reservation", {})


def _dates_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return a_start < b_end and a_end > b_start


def check_availability(check_in: str, check_out: str) -> dict:
    """Считает реально свободные домики по каждому типу через PMS API, плюс
    плановые закрытия и цену по ночам (чтобы модель не считала день недели
    сама — она в этом регулярно ошибается).

    Возвращает {"available_two_seat", "available_three_seat", "total_two_seat",
    "total_three_seat", "nights" (список {date, weekday_ru, rate}),
    "total_price_per_domik" (сумма rate по ночам, ОДИН домик, без доплат за
    детей), "closed_nights" (список ISO-дат из плановых закрытий — если
    непусто, эти конкретные ночи недоступны, ДАЖЕ если available_* больше 0,
    так как эти закрытия не бронирования и PMS API их не видит)}
    либо {"error": "..."} при некорректных датах или недоступности API.
    """
    try:
        start = dt.date.fromisoformat(check_in)
        end = dt.date.fromisoformat(check_out)
    except (ValueError, TypeError):
        return {"error": "Некорректные даты: нужен формат YYYY-MM-DD"}
    if start >= end:
        return {"error": "Дата заезда должна быть раньше даты выезда"}

    nights, total_price = _price_breakdown(start, end)
    closed_nights = _closed_nights(start, end)

    try:
        rooms = _get_rooms()
        room_type_by_id = {r["id"]: ROOM_TYPE_TO_HOUSE_TYPE.get(r.get("roomTypeId")) for r in rooms}
        total_two_seat = sum(1 for t in room_type_by_id.values() if t == "two_seat")
        total_three_seat = sum(1 for t in room_type_by_id.values() if t == "three_seat")

        occupied_two_seat: set[str] = set()
        occupied_three_seat: set[str] = set()

        for number in _search_active_reservation_numbers(start, end):
            reservation = _get_reservation(number)
            for stay in reservation.get("roomStays") or []:
                if stay.get("status") == "Cancelled":
                    continue
                room_id = stay.get("roomId")
                stay_start = (stay.get("checkInDateTime") or "")[:10]
                stay_end = (stay.get("checkOutDateTime") or "")[:10]
                if not room_id or not stay_start or not stay_end:
                    continue
                if not _dates_overlap(check_in, check_out, stay_start, stay_end):
                    continue
                house_type = room_type_by_id.get(room_id)
                if house_type == "two_seat":
                    occupied_two_seat.add(room_id)
                elif house_type == "three_seat":
                    occupied_three_seat.add(room_id)

        return {
            "available_two_seat": max(0, total_two_seat - len(occupied_two_seat)),
            "available_three_seat": max(0, total_three_seat - len(occupied_three_seat)),
            "total_two_seat": total_two_seat,
            "total_three_seat": total_three_seat,
            "nights": nights,
            "total_price_per_domik": total_price,
            "closed_nights": closed_nights,
        }
    except requests.RequestException:
        log.exception("Ошибка запроса к TravelLine PMS API")
        return {
            "error": "Не удалось получить данные от TravelLine PMS API",
            "nights": nights,
            "total_price_per_domik": total_price,
            "closed_nights": closed_nights,
        }
