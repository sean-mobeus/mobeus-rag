from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from memory.user_identity import get_user, upsert_user
from memory.session_memory import log_interaction

router = APIRouter()
class UserPayload(BaseModel):
    uuid: str
    name: Optional[str] = None

class InteractionPayload(BaseModel):
    uuid: str
    role: str
    message: str

@router.post("/api/user")
async def save_user(payload: UserPayload):
    try:
        upsert_user(payload.uuid, payload.name or "")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/user/{uuid}")
async def fetch_user(uuid: str):
    user = get_user(uuid)
    if user:
        return user
    raise HTTPException(status_code=404, detail="User not found")


@router.post("/api/user-identity/log-interaction")
async def log_user_interaction(payload: InteractionPayload):
    """Log a chat interaction for the given user."""
    try:
        log_interaction(payload.uuid, payload.role, payload.message)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

