import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Anthropic / Claude
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    claude_model: str = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    # Опционально: адрес прокси, совместимого с Anthropic API (например
    # https://api.proxyapi.ru/anthropic) — для оплаты в рублях без карты
    # зарубежного банка. Пусто = обращаться напрямую к api.anthropic.com.
    anthropic_base_url: str = os.environ.get("ANTHROPIC_BASE_URL", "").strip() or None

    # Avito
    avito_client_id: str = os.environ.get("AVITO_CLIENT_ID", "")
    avito_client_secret: str = os.environ.get("AVITO_CLIENT_SECRET", "")
    avito_user_id: str = os.environ.get("AVITO_USER_ID", "")

    # Telegram
    telegram_bot_token: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_admin_chat_id: str = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")

    # Firebase (проект самого агента: база знаний, переписки, сценарии)
    firebase_service_account_json: str = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    firebase_project_id: str = os.environ.get("FIREBASE_PROJECT_ID", "")

    # Firebase сайта бронирования (romatik-client2) — только для чтения
    # актуальной доступности домиков, отдельный проект и сервисный аккаунт.
    booking_firebase_service_account_json: str = os.environ.get("BOOKING_FIREBASE_SERVICE_ACCOUNT_JSON", "")
    booking_firebase_project_id: str = os.environ.get("BOOKING_FIREBASE_PROJECT_ID", "romantik-client")

    # Admin auth
    admin_username: str = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password: str = os.environ.get("ADMIN_PASSWORD", "")
    jwt_secret: str = os.environ.get("JWT_SECRET", "change-me-in-production")
    jwt_expires_minutes: int = int(os.environ.get("JWT_EXPIRES_MINUTES", "1440"))

    # Misc
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
