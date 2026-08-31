"""
Firestore access layer. Uses firebase-admin, initialized with a service
account. Can point at the SAME Firebase project used by romatik-client2 —
collections below are namespaced with an `avito_agent_` prefix specifically
so they never collide with that site's booking data.
"""

import json
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore

from app.config import get_settings

KNOWLEDGE_BASE_COLLECTION = "avito_agent_knowledge_base"
CONVERSATIONS_COLLECTION = "avito_agent_conversations"
SCENARIOS_COLLECTION = "avito_agent_scenarios"


@lru_cache
def get_db():
    settings = get_settings()
    if not firebase_admin._apps:
        if settings.firebase_service_account_json:
            # Either a path to a JSON key file, or the JSON contents themselves
            # (useful for platforms like Render/Railway where you paste the
            # whole key into one env var instead of shipping a file).
            raw = settings.firebase_service_account_json
            if raw.strip().startswith("{"):
                cred = credentials.Certificate(json.loads(raw))
            else:
                cred = credentials.Certificate(raw)
            firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id or None})
        else:
            # Falls back to Application Default Credentials (e.g. GOOGLE_APPLICATION_CREDENTIALS)
            firebase_admin.initialize_app()
    return firestore.client()
