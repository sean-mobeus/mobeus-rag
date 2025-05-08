import os
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
import uuid
import tempfile
from openai import OpenAI
from config import OPENAI_API_KEY
from pydantic import BaseModel
from rag import query_rag
import traceback

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


class QueryRequest(BaseModel):
    query: str

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
def speak_text(payload: QueryRequest):
    speech_file_path = "response.mp3"
    try:
        print(f"🗣 Generating TTS for: {payload.query}")
        speech_response = openai_client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=payload.query
        )
        print(f"✅ TTS call succeeded. Writing to {speech_file_path}")
        with open(speech_file_path, "wb") as f:
            f.write(speech_response.content)

        return FileResponse(speech_file_path, media_type="audio/mpeg")

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