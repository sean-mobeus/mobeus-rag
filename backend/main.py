import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
import uuid
import tempfile
from openai import OpenAI
from config import OPENAI_API_KEY, DEBUG_LOG_PATH
from pydantic import BaseModel
from rag import query_rag
import traceback
import json
from typing import Optional
from io import BytesIO
from routes import speak_stream
from routes import streaming_rag
from routes import user_identity_routes
from memory.session_memory import log_interaction
from routes.dashboard import debug_dashboard
from routes.dashboard import config_dashboard




app = FastAPI()
# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # frontend dev URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving
app.include_router(speak_stream.router)
app.include_router(streaming_rag.router)
app.include_router(user_identity_routes.router)
app.include_router(debug_dashboard.router)
app.include_router(config_dashboard.router)

# Initialize user table
from memory.user_identity import init_user_table
init_user_table()

# Initialize session memory table
from memory.session_memory import init_session_table
init_session_table()

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

class SpeakRequest(BaseModel):
    uuid: str
    text: Optional[str] = None
    query: Optional[str] = None

class QueryRequest(BaseModel):
    uuid: str
    query: str

class VoiceQueryRequest(BaseModel):
    uuid: str


@app.post("/api/voice-query")
async def voice_query(file: UploadFile = File(...), uuid: str = None):
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    transcript = openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=open(tmp_path, "rb")
    ).text

    from memory.session_memory import log_interaction
    log_interaction(uuid, "user", transcript)

    response = query_rag(transcript, uuid)
    log_interaction(uuid, "assistant", response["answer"])

    return {
        "transcript": transcript,
        **response
    }

@app.post("/api/speak")
async def speak_text(payload: SpeakRequest):
    tts_input = payload.text or payload.query
    if not tts_input:
        raise HTTPException(status_code=422, detail="Missing 'text' or 'query' in payload")

    try:
        print(f"🗣 Generating TTS for: {tts_input}")
        speech_response = openai_client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=tts_input
        )
        mp3_stream = BytesIO(speech_response.read())
        print(f"✅ TTS generated successfully")
        return StreamingResponse(mp3_stream, media_type="audio/mpeg")

    except Exception as e:
        print(f"❌ TTS error: {e}")
        return {"error": str(e)}

    except Exception as e:
        print(f"❌ TTS error: {e}")
        return {"error": str(e)}

@app.post("/api/query")
async def query_rag_endpoint(payload: QueryRequest):
    try:
        uuid = payload.uuid
        query = payload.query
        log_interaction(uuid, "user", query)  # ✅ Log user message
        response = query_rag(query, uuid)
        log_interaction(uuid, "assistant", response["answer"])  # ✅ Log assistant reply
        return response

    except Exception as e:
        print("❌ Exception occurred during RAG query:")
        traceback.print_exc()
        return {"error": str(e)}
