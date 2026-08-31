import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Anthropic / Claude
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    claude_model: str = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

    # Avito
    avito_client_id: str = os.environ.get("AVITO_CLIENT_ID", "")
    avito_client_secret: str = os.environ.get("AVITO_CLIENT_SECRET", "")
    avito_user_id: str = os.environ.get("AVITO_USER_ID", "")

    # Telegram
    telegram_bot_token: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_admin_chat_id: str = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")

    # Firebase
    firebase_service_account_json: str = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    firebase_project_id: str = os.environ.get("FIREBASE_PROJECT_ID", "")

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
