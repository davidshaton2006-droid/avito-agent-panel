import datetime as dt

from fastapi import APIRouter, Depends, HTTPException

from app.firestore_db import Channel, get_db, knowledge_base_collection
from app.models import KnowledgeBaseCreate, KnowledgeBaseEntry
from app.security import require_admin

router = APIRouter(
    prefix="/api/{channel}/knowledge-base", tags=["knowledge-base"], dependencies=[Depends(require_admin)]
)


@router.get("", response_model=list[KnowledgeBaseEntry])
def list_entries(channel: Channel):
    db = get_db()
    docs = db.collection(knowledge_base_collection(channel)).order_by("updatedAt", direction="DESCENDING").stream()
    return [KnowledgeBaseEntry(id=doc.id, **doc.to_dict()) for doc in docs]


@router.post("", response_model=KnowledgeBaseEntry)
def create_entry(channel: Channel, payload: KnowledgeBaseCreate):
    db = get_db()
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    data = {"question": payload.question, "answer": payload.answer, "updatedAt": now}
    ref = db.collection(knowledge_base_collection(channel)).document()
    ref.set(data)
    return KnowledgeBaseEntry(id=ref.id, **data)


@router.put("/{entry_id}", response_model=KnowledgeBaseEntry)
def update_entry(channel: Channel, entry_id: str, payload: KnowledgeBaseCreate):
    db = get_db()
    ref = db.collection(knowledge_base_collection(channel)).document(entry_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    data = {"question": payload.question, "answer": payload.answer, "updatedAt": now}
    ref.update(data)
    return KnowledgeBaseEntry(id=entry_id, **data)


@router.delete("/{entry_id}")
def delete_entry(channel: Channel, entry_id: str):
    db = get_db()
    ref = db.collection(knowledge_base_collection(channel)).document(entry_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    ref.delete()
    return {"ok": True}
