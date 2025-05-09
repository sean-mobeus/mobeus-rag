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




app = FastAPI()
# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # frontend dev URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

class SpeakRequest(BaseModel):
    text: Optional[str] = None
    query: Optional[str] = None

class QueryRequest(BaseModel):
    query: str


@app.post("/voice-query")
async def voice_query(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    transcript = openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=open(tmp_path, "rb")
    ).text

    # Send transcript to RAG
    response = query_rag(transcript)
    return {
        "transcript": transcript,
        **response
    }

@app.post("/speak")
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

@app.post("/query")
async def query_rag_endpoint(payload: QueryRequest):
    try:
        response = query_rag(payload.query)
        return response
    except Exception as e:
        print("❌ Exception occurred during RAG query:")
        traceback.print_exc()
        return {"error": str(e)}

@app.get("/")
def root():
    return {"message": "Mobeus RAG server is live"}


@app.get("/debug", response_class=HTMLResponse)
def get_debug_log():
    if not os.path.exists(DEBUG_LOG_PATH):
        return "<h2>No debug log found.</h2>"

    html = ["<h1>Mobeus Assistant — Debug Log</h1>"]
    with open(DEBUG_LOG_PATH, "r") as f:
        lines = f.readlines()

    for line in reversed(lines[-50:]):  # show last 50
        try:
            entry = json.loads(line)
            html.append(f"<h2>{entry['timestamp']}</h2>")
            html.append(f"<strong>Query:</strong> {entry['query']}<br>")
            html.append(f"<strong>Answer:</strong><pre>{entry['answer']}</pre>")
            html.append(f"<strong>Chunks:</strong><pre>{json.dumps(entry['top_chunks'], indent=2)}</pre>")
        except Exception as e:
            html.append(f"<p>Error parsing line: {e}</p>")

    return HTMLResponse(content="".join(html), status_code=200)