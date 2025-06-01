from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Response
from pydantic import BaseModel
from typing import Optional

from audio.provider import OpenAITTSProvider

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"service": "audio", "status": "healthy"}


class SynthesisRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    format: Optional[str] = None


@router.post("/synthesize")
async def synthesize_audio(request: SynthesisRequest):
    """Generate full audio for given text via TTS provider."""
    provider = OpenAITTSProvider()
    audio_bytes = await provider.synthesize(request.text, request.voice, request.format)
    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.websocket("/stream")
async def audio_stream(websocket: WebSocket):
    """WebSocket endpoint for streaming TTS audio frames."""
    await websocket.accept()
    try:
        data = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    text = data.get("text", "")
    voice = data.get("voice")
    provider = OpenAITTSProvider()
    try:
        async for chunk in provider.stream(text, voice, data.get("format")):
            await websocket.send_bytes(chunk)
    except WebSocketDisconnect:
        pass
    await websocket.close()
