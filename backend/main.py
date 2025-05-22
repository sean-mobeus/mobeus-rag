# Modified main.py with admin dashboard integration
import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
import uuid
import tempfile
from openai import OpenAI
from config import OPENAI_API_KEY, DEBUG_LOG_PATH
from pydantic import BaseModel
from vector.rag import query_rag
import traceback
import json
from typing import Optional
from io import BytesIO
from routes import speak_stream
from chat import streaming_rag
from routes import user_identity_routes
from routes import openai_realtime_tokens
from routes import realtime_chat
from memory.session_memory import log_interaction
# Dashboard imports disabled
# from stats import debug_dashboard
# from stats import config_dashboard
from chat import webrtc_signaling

# Dashboard integration disabled
# from dashboard_integration import setup_admin_dashboard

# Initialize database
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code here
    from memory.db import ensure_tables_exist
    
    if ensure_tables_exist():
        print("✅ FastAPI startup: Database tables initialized")
    else:
        print("⚠️ FastAPI startup: Database initialization failed...")
    
    yield  # Application runs here
    
    # Shutdown code here (if needed)
    print("🛑 Shutting down application")

app = FastAPI(lifespan=lifespan)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include existing routes (dashboards disabled)
app.include_router(speak_stream.router)
app.include_router(streaming_rag.router)
# Routes for user identity management (including log-interaction endpoint)
app.include_router(user_identity_routes.router)
# app.include_router(debug_dashboard.router)
# app.include_router(config_dashboard.router)  # Dashboard routes disabled
app.include_router(webrtc_signaling.router)
app.include_router(openai_realtime_tokens.router)
app.include_router(realtime_chat.router)

## Dashboard setup disabled
# setup_admin_dashboard(app, prefix="/admin")

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


@app.get("/test")
async def test_endpoint():
    return {"message": "Server is running"}


@app.post("/api/voice-query")
async def voice_query(file: UploadFile = File(...), uuid: Optional[str] = None):
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
        # Return proper HTTP error for front-end to catch
        raise HTTPException(status_code=500, detail=str(e))
    
## Admin dashboard endpoint disabled
## @app.get("/admin-dashboard")
## async def redirect_to_admin_dashboard():
##     """Redirect to the new admin dashboard"""
##     from fastapi.responses import RedirectResponse
##     return RedirectResponse(url="/admin/")

# Debug endpoint to list all routes
@app.get("/debug/routes")
async def list_routes():
    routes = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path is not None and methods is not None:
            routes.append({
                "path": path,
                "methods": list(methods)
            })
    return {"routes": routes}