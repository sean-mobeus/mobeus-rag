from fastapi import APIRouter
from chat.api import router as chat_api_router

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"service": "chat", "status": "healthy"}

# Mount the migrated chat endpoints (realtime & dashboard)
router.include_router(chat_api_router)
