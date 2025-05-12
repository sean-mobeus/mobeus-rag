from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from tts.streaming import stream_tts_from_openai

router = APIRouter()

@router.get("/api/speak-stream")
def speak_stream(text: str = Query(...), voice: str = "nova"):
    audio_stream = stream_tts_from_openai(text, voice)
    return StreamingResponse(audio_stream, media_type="audio/ogg")