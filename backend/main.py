# Cleaned main.py - Legacy POCs removed
import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import datetime
from openai import OpenAI
from config import OPENAI_API_KEY
from pydantic import BaseModel
from vector.rag import query_rag
import traceback
from typing import Optional
from io import BytesIO
from routes.chat_routes import router as chat_router
from routes.memory_routes import router as memory_router
from routes.audio_routes import router as audio_router
from routes.video_routes import router as video_router
from routes.rag_routes import router as rag_router
from routes.speech_routes import router as speech_router
from routes.stats_routes import router as stats_router
from chat import openai_realtime_tokens
from routes import user_identity_routes
from memory.session_memory import log_interaction
import logging
from config import runtime_config

# Enable dashboards
from stats.debug_dashboard import router as debug_dashboard_router
from stats.config_dashboard import router as config_dashboard_router
from stats.main_dashboard import router as main_dashboard_router
from stats.session_dashboard import router as session_dashboard_router
from stats.tools_dashboard import router as tools_dashboard_router


logging.basicConfig(level=logging.INFO)

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

# Include service routers
app.include_router(chat_router, prefix="/chat")
app.include_router(memory_router, prefix="/memory")
app.include_router(audio_router, prefix="/audio")
app.include_router(video_router, prefix="/video")
app.include_router(rag_router, prefix="/rag")
app.include_router(speech_router, prefix="/speech")
app.include_router(stats_router, prefix="/stats")

# Include legacy routes for backwards compatibility
app.include_router(openai_realtime_tokens.router)
app.include_router(user_identity_routes.router)

# Enable dashboards with /admin prefix
app.include_router(main_dashboard_router, prefix="/admin")      # /admin/ (main dashboard)
app.include_router(debug_dashboard_router, prefix="/admin")     # /admin/debug
app.include_router(config_dashboard_router, prefix="/admin")    # /admin/config
app.include_router(session_dashboard_router, prefix="/admin")   # /admin/sessions
app.include_router(tools_dashboard_router, prefix="/admin")      # /admin/tools


# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

class SpeakRequest(BaseModel):
    uuid: str
    text: Optional[str] = None
    query: Optional[str] = None

class QueryRequest(BaseModel):
    uuid: str
    query: str

@app.get("/test")
async def test_endpoint():
    return {"message": "Server is running"}

# Keep this for non-realtime TTS if needed
@app.post("/api/speak")
async def speak_text(payload: SpeakRequest):
    tts_voice = runtime_config.get("TTS_VOICE", "nova")
    tts_input = payload.text or payload.query
    if not tts_input:
        raise HTTPException(status_code=422, detail="Missing 'text' or 'query' in payload")

    try:
        print(f"🗣 Generating TTS for: {tts_input}")
        speech_response = openai_client.audio.speech.create(
            model="tts-1",
            voice=tts_voice,
            input=tts_input
        )
        mp3_stream = BytesIO(speech_response.read())
        print(f"✅ TTS generated successfully")
        return StreamingResponse(mp3_stream, media_type="audio/mpeg")

    except Exception as e:
        print(f"❌ TTS error: {e}")
        return {"error": str(e)}

# Keep this for non-realtime RAG queries if needed
@app.post("/api/query")
async def query_rag_endpoint(payload: QueryRequest):
    try:
        uuid = payload.uuid
        query = payload.query
        log_interaction(uuid, "user", query)
        response = query_rag(query, uuid)
        log_interaction(uuid, "assistant", response["answer"])
        return response

    except Exception as e:
        print("❌ Exception occurred during RAG query:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint to clear both session and persistent memory
@app.post("/api/clear-memory")
async def clear_memory_endpoint(payload: QueryRequest):  # Reusing QueryRequest which has uuid
    try:
        uuid = payload.uuid
        
        # Get current memory stats before clearing
        from memory.session_memory import get_session_memory_size, get_all_session_memory
        from memory.persistent_memory import get_summary, clear_summary
        
        session_size = get_session_memory_size(uuid)
        session_messages = len(get_all_session_memory(uuid))
        persistent_summary = get_summary(uuid)
        persistent_size = len(persistent_summary) if persistent_summary else 0
        
        # Clear both session and persistent memory
        from memory.session_memory import clear_session_memory
        clear_session_memory(uuid)
        clear_summary(uuid)
        
        print(f"🗑️ Cleared all memory for {uuid}: {session_messages} messages, {session_size + persistent_size} total chars")
        
        return {
            "success": True,
            "cleared": {
                "session_messages": session_messages,
                "session_chars": session_size,
                "persistent_chars": persistent_size,
                "total_chars": session_size + persistent_size
            }
        }

    except Exception as e:
        print(f"❌ Exception occurred during memory clear:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Debug endpoints - keep for troubleshooting
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

@app.get("/debug/chroma-info")
async def debug_chroma_info():
    """Debug ChromaDB collection contents"""
    from vector.rag import collection
    try:
        count = collection.count()
        sample_results = collection.get(limit=5)
        
        documents = sample_results.get("documents") if sample_results else None
        metadatas = sample_results.get("metadatas") if sample_results else None
        
        return {
            "collection_name": collection.name,
            "total_documents": count,
            "sample_documents": documents[:3] if documents else [],
            "sample_metadatas": metadatas[:3] if metadatas else []
        }
    except Exception as e:
        return {"error": str(e)}
    
@app.get("/debug/test-search")
async def debug_test_search(q: str = "Mobeus"):
    """Test ChromaDB search directly"""
    from vector.rag import collection
    try:
        results = collection.query(query_texts=[q], n_results=5)
        
        documents = results.get("documents") if results else None
        metadatas = results.get("metadatas") if results else None
        
        doc_list = documents[0] if documents and len(documents) > 0 else []
        meta_list = metadatas[0] if metadatas and len(metadatas) > 0 else []
        
        return {
            "query": q,
            "found_documents": len(doc_list),
            "documents": doc_list[:2],
            "metadatas": meta_list[:2]
        }
    except Exception as e:
        return {"error": str(e)}

# Configuration endpoint for debugging
@app.get("/debug/config")
async def debug_config():
    """Debug current configuration values"""
    return {
        "current_config": runtime_config.all_config(),
        "memory_limit": runtime_config.get("SESSION_MEMORY_CHAR_LIMIT"),
        "gpt_model": runtime_config.get("GPT_MODEL"),
        "realtime_model": runtime_config.get("REALTIME_MODEL"),
        "realtime_voice": runtime_config.get("REALTIME_VOICE")
    }

@app.get("/debug/session-data/{uuid}")
async def debug_session_data(uuid: str):
    """Debug session data retrieval"""
    try:
        from memory.session_memory import get_all_session_memory
        from memory.persistent_memory import get_summary
        
        conversation = get_all_session_memory(uuid)
        summary = get_summary(uuid)
        
        return {
            "uuid": uuid,
            "conversation_count": len(conversation) if conversation else 0,
            "conversation_preview": conversation[:2] if conversation else [],
            "summary_length": len(summary) if summary else 0,
            "summary_preview": summary[:200] if summary else "No summary"
        }
    except Exception as e:
        return {"error": str(e), "uuid": uuid}
    
@app.get("/debug/prompt-storage/{uuid}")
async def debug_prompt_storage_endpoint(uuid: str):
    """Debug prompt storage for a specific session UUID"""
    try:
        from memory.session_memory import debug_prompt_storage
        result = debug_prompt_storage(uuid)
        return {
            "uuid": uuid,
            "debug_result": result,
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "uuid": uuid,
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }

@app.get("/debug/conversation-data/{uuid}")
async def debug_conversation_data_endpoint(uuid: str):
    """Debug conversation data retrieval for Bug #2"""
    try:
        from memory.session_memory import get_all_session_memory
        from memory.db import get_connection, execute_db_operation
        
        # Get current session memory
        current_session = get_all_session_memory(uuid)
        
        # Get historical interaction logs
        def _get_historical():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT user_message, assistant_response, created_at, interaction_id
                        FROM interaction_logs
                        WHERE uuid = %s
                        ORDER BY created_at DESC
                        LIMIT 5
                    """, (uuid,))
                    
                    return [
                        {
                            "user_message": row[0][:100] + "..." if row[0] and len(row[0]) > 100 else row[0],
                            "assistant_response": row[1][:100] + "..." if row[1] and len(row[1]) > 100 else row[1],
                            "created_at": row[2].isoformat() if row[2] else None,
                            "interaction_id": row[3]
                        }
                        for row in cur.fetchall()
                    ]
        
        historical_data = execute_db_operation(_get_historical) or []
        
        return {
            "uuid": uuid,
            "current_session_count": len(current_session),
            "current_session_preview": current_session[:2] if current_session else [],
            "historical_interactions_count": len(historical_data),
            "historical_interactions_preview": historical_data,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        import traceback
        return {
            "uuid": uuid,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.datetime.now().isoformat()
        }
