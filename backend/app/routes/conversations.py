import datetime as dt

from fastapi import APIRouter, Depends, HTTPException

from app.avito_client import send_message
from app.firestore_db import CONVERSATIONS_COLLECTION, get_db
from app.models import Conversation, Message, SendMessageRequest
from app.security import require_admin
from app.telegram_notify import send_conversation_message

router = APIRouter(prefix="/api/conversations", tags=["conversations"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[Conversation])
def list_conversations():
    db = get_db()
    docs = db.collection(CONVERSATIONS_COLLECTION).order_by("updatedAt", direction="DESCENDING").stream()
    return [Conversation(id=doc.id, **doc.to_dict()) for doc in docs]


@router.get("/{conversation_id}", response_model=Conversation)
def get_conversation(conversation_id: str):
    db = get_db()
    doc = db.collection(CONVERSATIONS_COLLECTION).document(conversation_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    return Conversation(id=doc.id, **doc.to_dict())


@router.post("/{conversation_id}/send", response_model=Conversation)
def send_admin_message(conversation_id: str, payload: SendMessageRequest):
    """Manual message from the admin (e.g. final booking confirmation)."""
    db = get_db()
    ref = db.collection(CONVERSATIONS_COLLECTION).document(conversation_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    data = doc.to_dict()
    conversation = Conversation(id=doc.id, **data)

    send_message(conversation.chatId, payload.text)

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    conversation.messages.append(Message(role="admin", text=payload.text, timestamp=now))
    conversation.updatedAt = now
    ref.update({"messages": [m.model_dump() for m in conversation.messages], "updatedAt": now})
    send_conversation_message(f"🧑‍💼 {payload.text}", conversation.telegramThreadId)
    return conversation


@router.patch("/{conversation_id}/status", response_model=Conversation)
def set_status(conversation_id: str, status: str):
    if status not in ("open", "escalated", "closed"):
        raise HTTPException(status_code=400, detail="Некорректный статус")
    db = get_db()
    ref = db.collection(CONVERSATIONS_COLLECTION).document(conversation_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    ref.update({"status": status, "updatedAt": now})
    data = doc.to_dict()
    data["status"] = status
    data["updatedAt"] = now
    return Conversation(id=conversation_id, **data)
