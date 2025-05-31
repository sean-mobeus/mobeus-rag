from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from chat.orchestrator import realtime_chat, dashboard_websocket

router = APIRouter()

# Mount the chat WebSocket handlers
router.websocket("/realtime")(realtime_chat)
router.websocket("/admin/dashboard")(dashboard_websocket)