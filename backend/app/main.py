import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import auth, conversations, knowledge_base, scenarios, webhook

logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(title="Avito Agent Panel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(knowledge_base.router)
app.include_router(conversations.router)
app.include_router(scenarios.router)
app.include_router(webhook.router)


@app.get("/health")
def health():
    return {"status": "ok"}
