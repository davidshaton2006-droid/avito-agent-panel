from fastapi import APIRouter, Depends

from app.agent_settings import get_agent_settings, update_agent_settings
from app.firestore_db import Channel
from app.models import AgentSettings, AgentSettingsUpdate
from app.security import require_admin

router = APIRouter(prefix="/api/{channel}/settings", tags=["settings"], dependencies=[Depends(require_admin)])


@router.get("", response_model=AgentSettings)
def read_settings(channel: Channel):
    return AgentSettings(**get_agent_settings(channel))


@router.put("", response_model=AgentSettings)
def write_settings(channel: Channel, payload: AgentSettingsUpdate):
    patch = payload.model_dump(exclude_unset=True)
    return AgentSettings(**update_agent_settings(channel, patch))
