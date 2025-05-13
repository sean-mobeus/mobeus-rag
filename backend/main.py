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
app.include_router(streaming_rag.router)


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
    # Use the configured debug log path (consistent with DEBUG_LOG_PATH)
    log_path = DEBUG_LOG_PATH
    if not os.path.exists(log_path):
        return HTMLResponse("<h2>No log file found.</h2>", status_code=200)

    html = [
        "<head><title>Mobeus Assistant — Debug Log</title><style>",
        "body{font-family:sans-serif;padding:2rem;background:#f9f9f9}",
        "h1{margin-bottom:1rem}pre{background:#eee;padding:1rem;border-radius:6px;white-space:pre-wrap;word-break:break-word;overflow-x:auto;max-width:100%;display:block}",
        "details{border:1px solid #ccc;border-radius:8px;padding:1rem;background:#fff;margin-bottom:1rem}",
        "details summary{font-weight:bold;font-size:1rem;cursor:pointer;margin-bottom:0.5rem}",
        "details[open] summary::after{content:' ▲'}details summary::after{content:' ▼'}",
        ".metric{display:inline-block;margin-right:1rem;padding:0.3rem 0.5rem;border-radius:4px;background:#f0f0f0;margin-bottom:0.5rem}",
        ".good{color:green}.warning{color:orange}.bad{color:red}",
        ".metrics-grid{display:grid;grid-template-columns:repeat(auto-fill, minmax(180px, 1fr));gap:0.5rem}",
        "</style></head><body><h1>Mobeus Assistant — Debug Log</h1>",
        "<div style='margin-bottom:1rem'>",
        "<p><strong>Performance Targets:</strong> ",
        "<span class='metric good'>GPT &lt; 3s</span> ",
        "<span class='metric good'>TTS First Chunk &lt; 1.5s</span> ",
        "<span class='metric good'>Total &lt; 5s</span>",
        "</p></div>"
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
            
            # Enhanced timing display
            if timings:
                html.append("<strong>Performance Metrics:</strong>")
                html.append("<div class='metrics-grid'>")
                
                # Function to format timing values with appropriate color coding
                def format_metric(name, value, unit="s", thresholds=None):
                    if value is None:
                        return f"<div class='metric'><strong>{name}:</strong> N/A</div>"
                    
                    # Default thresholds if none provided
                    if thresholds is None:
                        if name == "gpt":
                            thresholds = (3.0, 5.0)  # good, warning
                        elif name == "tts_first_chunk":
                            thresholds = (1.5, 2.5)
                        elif name == "total":
                            thresholds = (5.0, 8.0)
                        elif name == "retrieval":
                            thresholds = (1.0, 2.0)
                        else:
                            thresholds = (2.0, 4.0)
                    
                    # Determine color based on thresholds
                    color_class = "good"
                    if value > thresholds[1]:
                        color_class = "bad"
                    elif value > thresholds[0]:
                        color_class = "warning"
                        
                    # Format the value and return the metric div
                    formatted_value = f"{value:.2f}" if isinstance(value, float) else value
                    return f"<div class='metric {color_class}'><strong>{name}:</strong> {formatted_value}{unit}</div>"
                
                # Total timing (most important)
                if "total" in timings:
                    html.append(format_metric("Total", timings["total"]))
                
                # GPT timing
                if "gpt" in timings:
                    html.append(format_metric("GPT", timings["gpt"]))
                
                # TTS timing metrics
                if "tts_first_chunk" in timings:
                    html.append(format_metric("TTS First Chunk", timings["tts_first_chunk"]))
                    perceived_latency = timings.get("tts_first_chunk", 0)
                    html.append(format_metric("Perceived Latency", perceived_latency, thresholds=(1.5, 3.0)))
                
                if "tts_total" in timings:
                    html.append(format_metric("TTS Total", timings["tts_total"]))
                
                # Retrieval timing
                if "retrieval" in timings:
                    html.append(format_metric("Retrieval", timings["retrieval"]))
                
                # Any other timing metrics
                for key, value in timings.items():
                    if key not in ["total", "gpt", "tts_first_chunk", "tts_total", "retrieval"]:
                        html.append(format_metric(key.replace("_", " ").title(), value))
                
                html.append("</div>")
                
                # New metrics added in our optimizations
                if "tts_bytes" in timings or "tts_chunks" in timings:
                    html.append("<div style='margin-top:0.5rem'>")
                    if "tts_bytes" in timings:
                        kb = timings["tts_bytes"] / 1024 if timings["tts_bytes"] else 0
                        html.append(f"<div class='metric'><strong>TTS Size:</strong> {kb:.1f} KB</div>")
                    if "tts_chunks" in timings:
                        html.append(f"<div class='metric'><strong>TTS Chunks:</strong> {timings['tts_chunks']}</div>")
                    html.append("</div>")
                
                # Still include the raw timings for detailed analysis
                html.append("<details><summary style='margin-top:0.5rem'>Raw Timing Data</summary>")
                html.append("<pre>" + json.dumps(timings, indent=2) + "</pre>")
                html.append("</details>")
            else:
                html.append("<pre><em>No timing data available</em></pre>")
            
            html.append("<strong>Top Chunks:</strong><br><pre>" + json.dumps(chunks, indent=2) + "</pre>")
            html.append("<details><summary style='margin-top:1rem'>🔍 RAW JSON</summary><pre>" + line + "</pre></details>")
            html.append("</div></details>")
        except Exception as e:
            html.append(f"<p>Error parsing line: {e}</p>")

    html.append("</body>")
    return HTMLResponse(content="".join(html), status_code=200)