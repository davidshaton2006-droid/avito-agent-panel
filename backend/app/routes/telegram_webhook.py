from fastapi import APIRouter, Header, HTTPException, Request

from app.config import get_settings
from app.telegram_bot import handle_update

router = APIRouter(tags=["telegram"])


@router.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    settings = get_settings()
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid secret token")

    update = await request.json()
    handle_update(update)
    return {"ok": True}
