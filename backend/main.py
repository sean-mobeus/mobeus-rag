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


app = FastAPI()
# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # frontend dev URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(speak_stream.router)


# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

class SpeakRequest(BaseModel):
    text: Optional[str] = None
    query: Optional[str] = None

class QueryRequest(BaseModel):
    query: str


@app.post("/api/voice-query")
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
    log_path = os.path.join(os.getcwd(), "rag_debug_fresh.jsonl")
    if not os.path.exists(log_path):
        return HTMLResponse("<h2>No log file found.</h2>", status_code=200)

    html = [
        "<head><title>Mobeus Assistant — Debug Log</title><style>",
        "body{font-family:sans-serif;padding:2rem;background:#f9f9f9}",
        "h1{margin-bottom:1rem}pre{background:#eee;padding:1rem;border-radius:6px;white-space:pre-wrap;word-break:break-word;overflow-x:auto;max-width:100%;display:block}",
        "details{border:1px solid #ccc;border-radius:8px;padding:1rem;background:#fff}",
        "details summary{font-weight:bold;font-size:1rem;cursor:pointer;margin-bottom:0.5rem}",
        "details[open] summary::after{content:' ▲'}details summary::after{content:' ▼'}",
        "</style></head><body><h1>Mobeus Assistant — Debug Log</h1>"
    ]

    try:
        with open(log_path, "r") as f:
            lines = reversed(f.readlines()[-50:])
    except Exception:
        return HTMLResponse("<h2>Error reading log file.</h2>", status_code=500)

    for line in lines:
        try:
            entry = json.loads(line)
            ts = entry.get("timestamp", "")
            q = entry.get("query", "")
            a = entry.get("answer", "")
            timings = entry.get("timings", {})
            chunks = entry.get("top_chunks", [])
            html.append(f"<details><summary><strong>{ts}</strong> — <em>{q}</em></summary><div>")
            html.append(f"<strong>Answer:</strong><br><pre>{a}</pre>")
            if timings:
                gpt_time = timings.get("gpt", 0)
                color = "red" if gpt_time > 5.0 else "green"
                html.append(f"<strong>Timings (sec):</strong><pre style='color:{color}'>" + json.dumps(timings, indent=2) + "</pre>")
            else:
                html.append("<pre><em>No timing data available</em></pre>")
            html.append("<strong>Top Chunks:</strong><br><pre>" + json.dumps(chunks, indent=2) + "</pre>")
            html.append("<details><summary style='margin-top:1rem'>🔍 RAW JSON</summary><pre>" + line + "</pre></details>")
            html.append("</div></details>")
        except Exception as e:
            html.append(f"<p>Error parsing line: {e}</p>")

    html.append("</body>")
    return HTMLResponse(content="".join(html), status_code=200)