from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from memory.user_identity import get_user, upsert_user

router = APIRouter()

class UserPayload(BaseModel):
    uuid: str
    name: str = None

@router.post("/api/user")
async def save_user(payload: UserPayload):
    try:
        upsert_user(payload.uuid, payload.name)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/user/{uuid}")
async def fetch_user(uuid: str):
    user = get_user(uuid)
    if user:
        return user
    raise HTTPException(status_code=404, detail="User not found")
