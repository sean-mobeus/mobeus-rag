from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio
import logging
import httpx
import websockets
from typing import Optional

from config import OPENAI_API_KEY
from rag import log_debug, retrieve_documents
from memory.persistent_memory import append_to_summary

router = APIRouter()

OPENAI_REALTIME_SESSIONS_URL = "https://api.openai.com/v1/realtime/sessions"
OPENAI_REALTIME_WS_URL = "wss://api.openai.com/v1/realtime"

async def create_realtime_session(instructions: Optional[str] = None):
    """Create a realtime session with OpenAI."""
    session_data = {
        "model": "gpt-4o-realtime-preview-2024-12-17",
        "voice": "alloy",
        "modalities": ["text", "audio"],
        "instructions": instructions or "",
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            OPENAI_REALTIME_SESSIONS_URL,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json=session_data,
        )
        resp.raise_for_status()
        return resp.json()

async def execute_tool(name: str, args: dict, user_uuid: Optional[str]):
    """Handle tool execution server-side."""
    if name == "search_knowledge_base":
        query = args.get("query", "")
        docs = await retrieve_documents(query)
        log_debug(query, docs[:3], "(realtime search)", {"tool": name})
        results = [
            {"content": d["text"], "source": d.get("source", ""), "relevance_score": d.get("score", 0)}
            for d in docs[:3]
        ]
        return {"results": results, "query": query, "total_results": len(docs)}
    elif name == "update_user_memory":
        append_to_summary(args.get("user_uuid") or user_uuid, args.get("information", ""))
        return {"success": True}
    return {"error": f"Unknown tool {name}"}

async def handle_function_call(event: dict, ws):
    name = event.get("name")
    call_id = event.get("call_id")
    args = {}
    if event.get("arguments"):
        try:
            args = json.loads(event["arguments"])
        except Exception:
            args = {}
    user_uuid = event.get("user_uuid")
    result = await execute_tool(name, args, user_uuid)
    response_event = {
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": json.dumps(result),
        },
    }
    await ws.send(json.dumps(response_event))
    await ws.send(
        json.dumps({"type": "response.create", "response": {"modalities": ["text", "audio"]}})
    )

@router.websocket("/api/realtime/chat")
async def realtime_chat(websocket: WebSocket):
    await websocket.accept()
    user_uuid = websocket.query_params.get("user_uuid")
    instructions = websocket.query_params.get("instructions")

    try:
        session = await create_realtime_session(instructions)
        token = session["client_secret"]["value"]
        model = session.get("model", "gpt-4o-realtime-preview-2024-12-17")
        openai_ws = await websockets.connect(
            f"{OPENAI_REALTIME_WS_URL}?model={model}",
            extra_headers={"Authorization": f"Bearer {token}"},
        )
        await websocket.send_json({"type": "session.created", "session": session})
    except Exception as e:
        await websocket.send_json({"type": "error", "error": str(e)})
        await websocket.close()
        return

    async def forward_from_openai():
        try:
            async for msg in openai_ws:
                await websocket.send_text(msg)
                try:
                    data = json.loads(msg)
                except Exception:
                    data = None
                if not data:
                    continue
                if data.get("type") == "response.function_call_arguments.done":
                    await handle_function_call(data, openai_ws)
                elif data.get("type") == "response.text.done":
                    log_debug("realtime", [], data.get("text", ""), {"event": "response"})
        finally:
            await websocket.close()

    async def forward_from_client():
        try:
            while True:
                data = await websocket.receive_text()
                await openai_ws.send(data)
        except WebSocketDisconnect:
            await openai_ws.close()
        except Exception:
            await openai_ws.close()

    await asyncio.gather(forward_from_openai(), forward_from_client())
