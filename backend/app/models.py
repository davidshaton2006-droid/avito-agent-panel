from typing import Literal, Optional

from pydantic import BaseModel, Field


class KnowledgeBaseEntry(BaseModel):
    id: Optional[str] = None
    question: str
    answer: str
    updatedAt: Optional[str] = None


class KnowledgeBaseCreate(BaseModel):
    question: str
    answer: str


class Message(BaseModel):
    role: Literal["guest", "agent", "admin", "system"]
    text: str
    timestamp: str
    imageUrl: Optional[str] = None


class Conversation(BaseModel):
    id: Optional[str] = None
    conversationId: str
    guestName: Optional[str] = None
    chatId: str
    itemId: Optional[str] = None
    messages: list[Message] = Field(default_factory=list)
    status: Literal["open", "escalated", "closed"] = "open"
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    # Scenario run state, if a scenario is currently in progress for this chat
    activeScenarioId: Optional[str] = None
    activeStepIndex: Optional[int] = None
    scenarioData: dict = Field(default_factory=dict)

    # Telegram forum topic this conversation is mirrored into, if any
    # (see telegram_notify.create_conversation_topic)
    telegramThreadId: Optional[int] = None


class ScenarioStep(BaseModel):
    type: Literal["message", "wait_photo", "wait_text", "notify_admin"]
    text: Optional[str] = None
    saveToField: Optional[str] = None


class Scenario(BaseModel):
    id: Optional[str] = None
    scenarioId: str
    name: Optional[str] = None
    triggerKeyword: str
    steps: list[ScenarioStep]
    isActive: bool = True
    updatedAt: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class SendMessageRequest(BaseModel):
    text: str
