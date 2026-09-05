import datetime as dt

from fastapi import APIRouter, Depends, HTTPException

from app.firestore_db import Channel, get_db, scenarios_collection
from app.models import Scenario
from app.security import require_admin

router = APIRouter(prefix="/api/{channel}/scenarios", tags=["scenarios"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[Scenario])
def list_scenarios(channel: Channel):
    db = get_db()
    docs = db.collection(scenarios_collection(channel)).stream()
    return [Scenario(id=doc.id, **doc.to_dict()) for doc in docs]


@router.put("/{scenario_id}", response_model=Scenario)
def update_scenario(channel: Channel, scenario_id: str, payload: Scenario):
    db = get_db()
    ref = db.collection(scenarios_collection(channel)).document(scenario_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Сценарий не найден")
    data = payload.model_dump(exclude={"id"})
    data["updatedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
    ref.update(data)
    return Scenario(id=scenario_id, **data)


@router.patch("/{scenario_id}/toggle", response_model=Scenario)
def toggle_scenario(channel: Channel, scenario_id: str):
    db = get_db()
    ref = db.collection(scenarios_collection(channel)).document(scenario_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Сценарий не найден")
    data = doc.to_dict()
    new_active = not data.get("isActive", True)
    ref.update({"isActive": new_active, "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat()})
    data["isActive"] = new_active
    return Scenario(id=scenario_id, **data)
